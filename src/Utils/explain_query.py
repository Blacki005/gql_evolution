def explain_graphql_query(schema_ast, query):
    from graphql import parse, build_ast_schema, print_ast, GraphQLSchema
    from graphql.language.ast import (
        DocumentNode, FieldNode, SelectionSetNode, OperationDefinitionNode,
        FragmentDefinitionNode, FragmentSpreadNode, InlineFragmentNode,
        ArgumentNode, VariableNode, ObjectValueNode, ObjectFieldNode, ListValueNode,
    )
    from graphql.type import (
        GraphQLObjectType, GraphQLInterfaceType, GraphQLUnionType,
        GraphQLNonNull, GraphQLList, GraphQLInputObjectType,
        GraphQLEnumType, GraphQLScalarType, GraphQLInputType, GraphQLNamedType,
    )

    schema: GraphQLSchema = build_ast_schema(schema_ast, assume_valid=True)

    # ---- popisy polí pro Object i Interface (výstup)
    field_meta: dict[tuple[str, str], str | None] = {}
    from graphql.language.ast import ObjectTypeDefinitionNode, InterfaceTypeDefinitionNode
    for defn in schema_ast.definitions:
        if isinstance(defn, (ObjectTypeDefinitionNode, InterfaceTypeDefinitionNode)):
            parent = defn.name.value
            for fld in defn.fields or []:
                desc = fld.description.value if fld.description else None
                field_meta[(parent, fld.name.value)] = desc

    query_ast: DocumentNode = parse(query)

    # ---- definice fragmentů (vstup i výstup)
    fragments: dict[str, FragmentDefinitionNode] = {
        d.name.value: d
        for d in query_ast.definitions
        if isinstance(d, FragmentDefinitionNode)
    }

    # ---------- UTILS ----------

    def unwrap(gtype: GraphQLInputType | GraphQLNamedType):
        while isinstance(gtype, (GraphQLNonNull, GraphQLList)):
            gtype = gtype.of_type
        return gtype

    def type_to_str(gtype) -> str:
        if isinstance(gtype, GraphQLNonNull):
            return f"{type_to_str(gtype.of_type)}!"
        if isinstance(gtype, GraphQLList):
            return f"[{type_to_str(gtype.of_type)}]"
        return getattr(gtype, "name", str(gtype))

    def type_node_to_str(type_node) -> str:
        k = getattr(type_node, "kind", None) or type_node.kind
        if k in ("NamedType", "named_type"):
            return type_node.name.value
        if k in ("NonNullType", "non_null_type"):
            return f"{type_node_to_str(type_node.type)}!"
        if k in ("ListType", "list_type"):
            return f"[{type_node_to_str(type_node.type)}]"
        raise ValueError(f"Unknown kind {k}")

    # ---------- 1) @param: popisy proměnných + (nově) mapování proměnná → skutečný input typ ----------

    # Proměnná může být použita kdekoli (i uvnitř objektů). Najdeme všechny použití a určíme typ.
    var_to_input_type: dict[str, GraphQLInputType] = {}

    def map_variable_usage_in_args(sel: FieldNode, parent_type):
        """Promapuje VariableNode ve všech argumentech fieldů (vč. vnořených objektů)."""
        if not isinstance(parent_type, (GraphQLObjectType, GraphQLInterfaceType)):
            return
        fdef = parent_type.fields.get(sel.name.value)
        if not fdef:
            return
        # Pro každý argument v AST porovnej s typem z fdef.args a rekurzivně projdi hodnoty:
        for arg in sel.arguments or []:
            arg_name = arg.name.value
            arg_def = fdef.args.get(arg_name)
            if not arg_def:
                continue
            def walk_value(value_node, expected_type: GraphQLInputType):
                if isinstance(value_node, VariableNode):
                    var_to_input_type[value_node.name.value] = expected_type
                    return
                unwrapped = unwrap(expected_type)
                if isinstance(value_node, ObjectValueNode) and isinstance(unwrapped, GraphQLInputObjectType):
                    # projdi pole objektu
                    for of in value_node.fields or []:
                        f: ObjectFieldNode = of
                        if f.name.value in unwrapped.fields:
                            walk_value(f.value, unwrapped.fields[f.name.value].type)
                elif isinstance(value_node, ListValueNode) and isinstance(expected_type, GraphQLList):
                    # každý prvek seznamu má typ .of_type
                    for v in value_node.values or []:
                        walk_value(v, expected_type.of_type)
                # skalár/enum: nic dalšího

            walk_value(arg.value, arg_def.type)

    # Projdi celý selection strom a hledej použití proměnných u argumentů
    def walk_for_var_types(sel_set: SelectionSetNode, parent_type):
        if not sel_set:
            return
        for sel in sel_set.selections:
            if isinstance(sel, FieldNode):
                map_variable_usage_in_args(sel, parent_type)
                # rekurze do dítěte
                if isinstance(parent_type, (GraphQLObjectType, GraphQLInterfaceType)):
                    fdef = parent_type.fields.get(sel.name.value)
                    if fdef and sel.selection_set:
                        walk_for_var_types(sel.selection_set, unwrap(fdef.type))
            elif isinstance(sel, FragmentSpreadNode):
                frag = fragments.get(sel.name.value)
                if frag:
                    new_parent = parent_type
                    if frag.type_condition:
                        tname = frag.type_condition.name.value
                        new_parent = schema.get_type(tname) or parent_type
                    walk_for_var_types(frag.selection_set, new_parent)
            elif isinstance(sel, InlineFragmentNode):
                new_parent = parent_type
                if sel.type_condition:
                    tname = sel.type_condition.name.value
                    new_parent = schema.get_type(tname) or parent_type
                walk_for_var_types(sel.selection_set, new_parent)

    for defn in query_ast.definitions:
        if isinstance(defn, OperationDefinitionNode):
            op = getattr(defn.operation, "value", defn.operation)
            root = {"query": schema.query_type,
                    "mutation": schema.mutation_type,
                    "subscription": schema.subscription_type}.get(op)
            if root:
                walk_for_var_types(defn.selection_set, root)

    # @param řádky (původní + přesnější typy)
    var_lines: list[str] = []
    for defn in query_ast.definitions:
        if isinstance(defn, OperationDefinitionNode) and defn.variable_definitions:
            for vdef in defn.variable_definitions:
                name = vdef.variable.name.value
                # preferuj typ podle skutečného použití:
                gtype = var_to_input_type.get(name)
                type_str = type_to_str(gtype) if gtype else type_node_to_str(vdef.type)
                
                base_named = unwrap(gtype) if gtype is not None else None
                desc = getattr(base_named, "description", None) if base_named else "missing description"
                if desc is not None:
                    desc = desc.replace("\n", "\n#\t")
                # desc = "\n#\t ".join(desc.split()) if desc else "missing description"
                
                # desc = field_meta.get((parent_type.name, fname))
                # zkus popis z odpovídajícího InputObjectField, pokud máme typ i shodu jména pole
                # (nelze spolehlivě – proměnná nemusí odpovídat názvu input fieldu)
                var_lines.append(f"# @param {{{type_str}}} {name} - {desc}")

    # ---------- 2) @input: struktura proměnných (včetně vnoření a rekurze) ----------

    input_lines: list[str] = []

    def append_input_line(path: str, gtype: GraphQLInputType, descr: str | None = None):
        d = (" - " + " ".join(descr.split())) if descr else ""
        input_lines.append(f"# @input {{{type_to_str(gtype)}}} {path}{d}")

    def describe_input_type(path: str, gtype: GraphQLInputType,
                            visiting: set[str] | None = None, depth: int = 0, max_depth: int = 1):
        """Vypíše strukturu input typu; chrání se proti rekurzi."""
        if depth > max_depth:
            input_lines.append(f"# @input {{...}} {path} - (truncated)")
            return
        visiting = visiting or set()

        if isinstance(gtype, GraphQLNonNull) or isinstance(gtype, GraphQLList):
            # vypiš wrapper typ a pokračuj do vnitřku
            append_input_line(path, gtype)
            inner = gtype.of_type
            # pro seznam můžeme označit subpath jako path[] (jen esteticky)
            child_path = path + "[]" if isinstance(gtype, GraphQLList) else path
            describe_input_type(child_path, inner, visiting, depth+1, max_depth)
            return

        base = unwrap(gtype)

        # Enum: vypiš s výčtem hodnot
        if isinstance(base, GraphQLEnumType):
            vals = "|".join(v.name for v in base.values.values())
            append_input_line(path, gtype, f"enum: {vals}")
            return

        # Scalar: jen řádka
        if isinstance(base, GraphQLScalarType):
            append_input_line(path, gtype)
            return

        # Input objekt
        if isinstance(base, GraphQLInputObjectType):
            if base.name in visiting:
                append_input_line(path, gtype, f"(recursive {base.name})")
                return
            visiting.add(base.name)

            # nejdřív řádek pro samotný uzel
            append_input_line(path, gtype, base.description)

            # potom pole
            for fname, fdef in base.fields.items():
                fpath = f"{path}.{fname}"
                append_input_line(fpath, fdef.type, fdef.description)
                # rekurze jen pokud je to zase objekt
                if isinstance(unwrap(fdef.type), GraphQLInputObjectType) or isinstance(unwrap(fdef.type), GraphQLList):
                    describe_input_type(fpath, fdef.type, visiting, depth+1, max_depth)

            visiting.remove(base.name)
            return

        # Fallback
        append_input_line(path, gtype)

    # spusť popis pro každou proměnnou, kterou jsme našli v dotazu
    # for var_name, gtype in var_to_input_type.items():
    #     describe_input_type(var_name, gtype)

    # ---------- 3) @property výstup (s fragmenty) ----------

    out_lines: list[str] = []
    seen: set[tuple[str, str]] = set()

    def print_field(parent_type, fname: str, path: str):
        if isinstance(parent_type, (GraphQLObjectType, GraphQLInterfaceType)):
            fld_def = parent_type.fields.get(fname)
        else:
            fld_def = None
        if not fld_def:
            return
        base_type = unwrap(fld_def.type)
        base_name = getattr(base_type, "name", "Object")
        desc = field_meta.get((parent_type.name, fname)) or ""
        desc = " ".join(desc.split()) if desc else ""
        key = (path, base_name)
        if key in seen:
            return
        seen.add(key)
        out_lines.append(f'# @property {{{base_name}}} {path}' + (f' - {desc}' if desc else ''))

    def walk_out(sel_set: SelectionSetNode, parent_type, prefix: str):
        if not sel_set:
            return
        for sel in sel_set.selections:
            if isinstance(sel, FieldNode):
                fname = sel.name.value
                path = f"{prefix}.{fname}" if prefix else fname
                if isinstance(parent_type, GraphQLUnionType):
                    continue
                print_field(parent_type, fname, path)
                if sel.selection_set and isinstance(parent_type, (GraphQLObjectType, GraphQLInterfaceType)):
                    fdef = parent_type.fields.get(fname)
                    if fdef:
                        walk_out(sel.selection_set, unwrap(fdef.type), path)
            elif isinstance(sel, FragmentSpreadNode):
                frag = fragments.get(sel.name.value)
                if frag:
                    new_parent = parent_type
                    if frag.type_condition:
                        tname = frag.type_condition.name.value
                        new_parent = schema.get_type(tname) or parent_type
                    walk_out(frag.selection_set, new_parent, prefix)
            elif isinstance(sel, InlineFragmentNode):
                new_parent = parent_type
                if sel.type_condition:
                    tname = sel.type_condition.name.value
                    new_parent = schema.get_type(tname) or parent_type
                walk_out(sel.selection_set, new_parent, prefix)

    for defn in query_ast.definitions:
        if isinstance(defn, OperationDefinitionNode):
            op = getattr(defn.operation, "value", defn.operation)
            root = {"query": schema.query_type,
                    "mutation": schema.mutation_type,
                    "subscription": schema.subscription_type}.get(op)
            if root:
                walk_out(defn.selection_set, root, "")

    # ---------- 4) Sestavení hlavičky + dotaz ----------

    header = []
    if var_lines:
        header.append("# ")
        header.extend(var_lines)
    if input_lines:
        header.append("# ")
        header.append("# @input structure")
        header.extend(input_lines)
    header.append("# @returns {Object}")
    if out_lines:
        header.append("# ")
        header.extend(out_lines)

    return "\n".join(header + ["", print_ast(query_ast)])
