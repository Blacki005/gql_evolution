from pathlib import Path
from typing import List, Dict, Tuple
from collections import deque
from graphql.language.ast import (
    DocumentNode,
    NamedTypeNode, 
    NonNullTypeNode, 
    ListTypeNode,
)
from graphql import build_ast_schema

from .utils_sdl_2 import (
    build_medium_fragment, 
    get_read_vector_values, 
    select_ast_by_path, 
    get_read_scalar_values,
    build_large_fragment
)

class GraphQLQueryBuilder:
    def __init__(self, sdl_ast: DocumentNode = None, disabled_fields: list[str]=[]):

        self.ast = sdl_ast
        self.schema = build_ast_schema(self.ast, assume_valid=True)
        self.adjacency = self._build_adjacency(self.ast, disabled_fields)

    def _unwrap_type(self, t):
        # Unwrap AST type nodes (NonNull, List) to get NamedTypeNode
        while isinstance(t, (NonNullTypeNode, ListTypeNode)):
            t = t.type
        if isinstance(t, NamedTypeNode):
            return t.name.value
        raise TypeError(f"Unexpected type node: {t}")

    def _build_adjacency(self, ast, disabled_fields: list[str]) -> Dict[str, List[Tuple[str, str]]]:
        edges: Dict[str, List[Tuple[str, str]]] = {}
        for defn in ast.definitions:
            if hasattr(defn, 'fields'):
                from_type = defn.name.value
                for field in defn.fields:
                    if field.name.value in disabled_fields:
                        continue
                    to_type = self._unwrap_type(field.type)
                    edges.setdefault(from_type, []).append((field.name.value, to_type))
        return edges

    def _find_path(self, source: str, target: str) -> List[Tuple[str, str]]:
        queue = deque([(source, [])])
        visited = {source}
        while queue:
            current, path = queue.popleft()
            for field, nxt in self.adjacency.get(current, []):
                if nxt == target:
                    return path + [(field, nxt)]
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, path + [(field, nxt)]))
        return []

    def build_query_vector(self, page_operation:str=None, types: List[str]=[]) -> str:
        print(f"building query vector for types {types}")
        root = types[0]
        rootfragment = build_large_fragment(self.ast, root)
        page_operations = get_read_vector_values(self.ast)
        if page_operation is None:
            page_operation = page_operations[root][0]
        # print(f"page_operation {page_operation}")

        field = select_ast_by_path(self.ast, ["Query", page_operation])
        
        # args = [(f"${arg.name.value}: {arg.type.name.value}" + ("!" if isinstance(arg.type, NonNullTypeNode) else "")) for arg in field.arguments]
        args = [f"${arg.name.value}: {self.type_node_to_str(arg.type)}" for arg in field.arguments if field.arguments]
        args_str = ", ".join(args)
        args2 = [(f"{arg.name.value}: ${arg.name.value}") for arg in field.arguments]
        args2_str = ", ".join(args2)
        args3 = [
            (
                f"# ${arg.name.value}: {self.type_node_to_str(arg.type)}" + 
                f" # {arg.description.value if arg.description else ''}"
            )
            for arg in field.arguments
        ]
        args3_str = "\n".join(args3)
        args3_str += "\n\n# to get more results, adjust parameters $skip and / or $limit and call the query until the result is empty vector\n"
        # print(f"args: {args}")

        # print(f"field: {field}, {field.name.value}")
        # Generate fragment definitions for each type
        fragments = [
            build_medium_fragment(self.ast, t)
            for t in types
        ]
        # Precompute full paths from root to each target
        full_paths = {t: self._find_path(root, t) for t in types[1:]}

        def build_spread(current: str, remaining_path: List[Tuple[str, str]]) -> str:
            # If no more path, insert fragment spread
            if not remaining_path:
                return f"...{current}MediumFragment"
            field, next_type = remaining_path[0]
            sub = build_spread(next_type, remaining_path[1:])
            return f"{field} {{ {sub} }}"

        # Build selection sets for each target and combine
        selections = [
            build_spread(root, path)
            for path in full_paths.values()
        ]
        # selections.append(rootfragment)

        unique_selections = list(dict.fromkeys(selections))
        selection_str = "\n   ".join(unique_selections)
        query = f"query {page_operation}({args_str})\n{args3_str}\n{{\n   {page_operation}({args2_str})\n   {{\n    ...{root}MediumFragment\n ...{root}LargeFragment\n    {selection_str} \n   }} \n}}"
        # Append fragments after the main query
        fragments_str = "\n\n".join(fragments)
        result = f"{query}\n\n{fragments_str}\n\n{rootfragment}"
        print(f"vector query \n{result}")
        return result
    
    def type_node_to_str(self, type_node):
        if isinstance(type_node, NonNullTypeNode):
            return self.type_node_to_str(type_node.type) + "!"
        elif isinstance(type_node, ListTypeNode):
            return "[" + self.type_node_to_str(type_node.type) + "]"
        elif isinstance(type_node, NamedTypeNode):
            return type_node.name.value
        else:
            raise TypeError(f"Unknown type node: {type(type_node)}")

    def type_node_to_name(self, type_node):
        if isinstance(type_node, NonNullTypeNode):
            return self.type_node_to_str(type_node.type)
        elif isinstance(type_node, ListTypeNode):
            return self.type_node_to_str(type_node.type)
        elif isinstance(type_node, NamedTypeNode):
            return type_node.name.value
        else:
            raise TypeError(f"Unknown type node: {type(type_node)}")

    def build_query_scalar(self, page_operation:str=None, types: List[str]=[]) -> str:
        
            
        print(f"building query scalar for types {types}")
        root = types[0]
        rootfragment = build_large_fragment(self.ast, root)
        page_operations = get_read_scalar_values(self.ast)
        if page_operation is None:
            page_operation = page_operations[root][0] 
        # print(f"page_operation {page_operation}")

        field = select_ast_by_path(self.ast, ["Query", page_operation])
        if field is None:
            raise ValueError(f"Field {page_operation} not found in Query type")
        # args = [(f"${arg.name.value}: {arg.type.name.value}" + ("!" if isinstance(arg.type, NonNullTypeNode) else "")) for arg in field.arguments]
        args = [f"${arg.name.value}: {self.type_node_to_str(arg.type)}" for arg in field.arguments if field.arguments]
        args_str = ", ".join(args)
        args2 = [(f"{arg.name.value}: ${arg.name.value}") for arg in field.arguments]
        args2_str = ", ".join(args2)
        # print(f"args: {args}")
        args3 = [
            (
                f"# ${arg.name.value}: {self.type_node_to_str(arg.type)}" + 
                f" # {arg.description.value if arg.description else ''}"
            )
            for arg in field.arguments
        ]
        args3_str = "\n".join(args3)

        # print(f"field: {field}, {field.name.value}")
        # Generate fragment definitions for each type
        fragments = [
            build_medium_fragment(self.ast, t)
            for t in types
        ]
        fragments.append(rootfragment)
        # Precompute full paths from root to each target
        full_paths = {t: self._find_path(root, t) for t in types[1:]}

        def build_spread(current: str, remaining_path: List[Tuple[str, str]]) -> str:
            # If no more path, insert fragment spread
            if not remaining_path:
                return f"...{current}MediumFragment"
            field, next_type = remaining_path[0]
            sub = build_spread(next_type, remaining_path[1:])
            return f"{field} {{ {sub} }}"

        # Build selection sets for each target and combine
        selections = [
            build_spread(root, path)
            for path in full_paths.values()
        ]
        unique_selections = list(dict.fromkeys(selections))
        selection_str = " ".join(unique_selections)
        query = f"query {page_operation}({args_str})\n{args3_str}\n{{\n   {page_operation}({args2_str})\n   {{\n    ...{root}MediumFragment\n    ...{root}LargeFragment\n    {selection_str} \n   }} \n}}"
        # Append fragments after the main query
        fragments_str = "\n\n".join(fragments)
        return f"{query}\n\n{fragments_str}"    

