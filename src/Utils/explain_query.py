def explain_graphql_query(schema_sdl: str, query: str) -> None:
    from graphql import (
        parse,
        build_ast_schema,
        print_ast
    )
    from graphql.language import DocumentNode, FieldNode
    from graphql.language.visitor import visit
    from graphql.utilities import TypeInfo
    from graphql import parse, build_ast_schema, TypeInfo, visit, GraphQLSchema
    from graphql.language.visitor import visit
    from graphql.language.ast import (
        DocumentNode,
        FieldNode,
        SelectionSetNode,
        OperationDefinitionNode,
    )
    from graphql.type.definition import (
        GraphQLObjectType,
        GraphQLNonNull,
        GraphQLList,
    )

    schema_ast = parse(schema_sdl)
    schema = build_ast_schema(schema_ast, assume_valid=True)

    # map description z AST schématu
    field_meta: dict[tuple[str,str], str|None] = {}
    for defn in schema_ast.definitions:
        from graphql.language.ast import ObjectTypeDefinitionNode
        if isinstance(defn, ObjectTypeDefinitionNode):
            parent = defn.name.value
            for fld in defn.fields or []:
                desc = fld.description.value if fld.description else None
                field_meta[(parent, fld.name.value)] = desc
                    
    query = """
query eventPage($skip: Int, $limit: Int, $orderby: String, $where: EventInputFilter) {
  eventPage(skip: $skip, limit: $limit, orderby: $orderby, where: $where) {
  ...Event
}
}

fragment EventInvitation on EventInvitationGQLModel {
  __typename
  id
  lastchange
  created
  createdbyId
  changedbyId
  rbacobjectId
  createdby { __typename }
  changedby { __typename }
  rbacobject { __typename }
  eventId
  userId
  stateId
  event { __typename }
  user { __typename }
  }

fragment Event on EventGQLModel {
__typename
id
lastchange
created
createdbyId
changedbyId
rbacobjectId
path
name
nameEn
description
startdate
enddate
duration_raw
valid
place
facilityId
mastereventId
subevents { __typename }
userInvitations {
  ...EventInvitation
}
# duration
}
    """

    # parse → AST (DocumentNode)
    query_ast = parse(query)

    # vytisknout strom
    print(query_ast)
    # nebo jako JSON
    import json
    def node_to_dict(node):
        # graphql-core AST nodes mají `.to_dict()` na Python 3.10+:
        return node.to_dict()

    print(json.dumps(node_to_dict(query_ast), indent=2))

    # zpět na string
    print(print_ast(query_ast))

    def unwrap_type(gtype):
        """Strip away NonNull and List wrappers to get the base Named type."""
        while isinstance(gtype, (GraphQLNonNull, GraphQLList)):
            gtype = gtype.of_type
        return gtype

    def type_node_to_str(type_node) -> str:
        """Renders a VariableDefinitionNode.type back to a string."""
        kind = type_node.kind  # e.g. 'NonNullType', 'ListType', or 'NamedType'
        if kind in ["NamedType", "named_type"]:
            return type_node.name.value
        if kind in ["NonNullType", "non_null_type"]:
            return f"{type_node_to_str(type_node.type)}!"
        if kind in ["ListType", "list_type"]:
            return f"[{type_node_to_str(type_node.type)}]"
        raise ValueError(f"Unknown kind {kind}")
    
    def print_query_with_header_comments(query_ast: DocumentNode, schema: GraphQLSchema) -> str:
        # 1) Gather input (variable) descriptions
        var_lines: list[str] = []

        for defn in query_ast.definitions:
            if isinstance(defn, OperationDefinitionNode) and defn.variable_definitions:
                # Předpokládáme, že dotaz obsahuje právě jedno root pole, např. userById
                root_sel = next(
                    (s for s in defn.selection_set.selections if isinstance(s, FieldNode)),
                    None
                )
                if not root_sel:
                    continue

                root_field_name = root_sel.name.value
                # query_type, mutation_type nebo subscription_type dle defn.operation
                root_type_map = {
                    "QUERY":       schema.query_type,
                    "mutation":    schema.mutation_type,
                    "subscription": schema.subscription_type
                }
                root_type = root_type_map[defn.operation.name]
                root_field_def = root_type.fields.get(root_field_name)

                for var_def in defn.variable_definitions:  # type: VariableDefinitionNode
                    name     = var_def.variable.name.value     # např. "id"
                    type_str = type_node_to_str(var_def.type)  # např. "UUID!"
                    # najdi popis argumentu
                    desc = None
                    if root_field_def and name in root_field_def.args:
                        arg_def = root_field_def.args[name]
                        desc = arg_def.description
                    # očisti whitespace
                    if desc:
                        desc = " ".join(desc.split())
                        var_lines.append(f"# @param {{{type_str}}} {name} - {desc}")
                    else:
                        var_lines.append(f"# @param {{{type_str}}} {name}")


        # 2) Gather output (field) descriptions with full dotted path
        out_lines: list[str] = []
        def walk(
            sel_set: SelectionSetNode,
            parent_type: GraphQLObjectType,
            prefix: str
        ):
            for sel in sel_set.selections:
                if not isinstance(sel, FieldNode):
                    continue
                fname = sel.name.value
                path  = f"{prefix}.{fname}" if prefix else fname

                fld_def = parent_type.fields.get(fname)
                if not fld_def:
                    continue

                # unwrap to get the NamedType
                base_type = unwrap_type(fld_def.type)  # GraphQLNamedType
                # fetch the description and normalize whitespace
                desc = field_meta.get((parent_type.name, fname))
                if desc:
                    desc = " ".join(desc.split())
                    # from:
                    # out_lines.append(f'# @property {{""}} {path} - {desc}')
                    # to:
                    out_lines.append(f'# @property {{{base_type.name}}} {path} - {desc}')

                # recurse into nested selections
                if sel.selection_set and isinstance(base_type, GraphQLObjectType):
                    walk(sel.selection_set, base_type, path)

        for defn in query_ast.definitions:
            if isinstance(defn, OperationDefinitionNode):
                # print(f"schema: \n{dir(schema)}")
                root_map = {
                    "QUERY": schema.query_type,
                    "mutation": schema.mutation_type,
                    "subscription": schema.subscription_type
                }
                root = root_map[defn.operation.name]
                walk(defn.selection_set, root, prefix="")

        # 3) Build the header block
        header = []
        if var_lines:
            header.append("# ")
            header.extend(var_lines)
        header.append("# @returns {Object}")
        if out_lines:
            header.append("# ")
            header.extend(out_lines)

        # 4) Print the actual query (unmodified) below
        query_str = print_ast(query_ast)

        return "\n".join(header + ["", query_str])  
    
    query_with_header_comments = print_query_with_header_comments(query_ast=query_ast, schema=schema)
    print(f"query_with_header_comments: \n{query_with_header_comments}")
    return query_with_header_comments
