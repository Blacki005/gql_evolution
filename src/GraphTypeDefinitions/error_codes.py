"""
Centrální slovník chybových kódů pro GraphQL mutace.

Každý chybový kód je unikátní UUID identifikující konkrétní chybový stav.
Tyto kódy se používají v InsertError, UpdateError a DeleteError pro konzistentní
error handling napříč celou aplikací.

Struktura:
- code: Unikátní UUID identifikátor chyby
- msg: Lidsky čitelný popis chyby
- location: Název mutace/operace kde může nastat
"""
import typing
from dataclasses import dataclass


@dataclass
class ErrorCode:
    """Struktura pro definici chybového kódu"""
    code: str  # UUID
    msg: str   # Chybová zpráva
    location: str  # Kde se chyba vyskytuje


# ============================================
# DOCUMENT ERROR CODES
# ============================================


DOCUMENT_INSERT_UNAUTHORIZED = ErrorCode(
    code="a1b2c3d4-1111-4001-8001-000000000003",
    msg="You are not authorized to insert documents",
    location="Document_insert"
)

DOCUMENT_INSERT_RBAC_MISSING = ErrorCode(
    code="a1b2c3d4-1111-4001-8001-000000000004",
    msg="RBAC object not found or access denied",
    location="Document_insert"
)

DOCUMENT_UPDATE_STALE_DATA = ErrorCode(
    code="a1b2c3d4-2222-4002-8002-000000000012",
    msg="Document was modified by another user. Please refresh and try again.",
    location="Document_update"
)

DOCUMENT_UPDATE_UNAUTHORIZED = ErrorCode(
    code="a1b2c3d4-2222-4002-8002-000000000013",
    msg="You are not authorized to update this document",
    location="Document_update"
)

DOCUMENT_UPDATE_CLASSIFICATION_INVALID = ErrorCode(
    code="a1b2c3d4-2222-4002-8002-000000000014",
    msg="Invalid classification value",
    location="Document_update_classification"
)

DOCUMENT_UPDATE_CLASSIFICATION_UNAUTHORIZED = ErrorCode(
    code="a1b2c3d4-2222-4002-8002-000000000015",
    msg="You are not authorized to change document classification",
    location="Document_update_classification"
)

DOCUMENT_DELETE_UNAUTHORIZED = ErrorCode(
    code="a1b2c3d4-3333-4003-8003-000000000022",
    msg="You are not authorized to delete this document",
    location="Document_delete"
)


# ============================================
# FRAGMENT ERROR CODES
# ============================================

FRAGMENT_INSERT_NO_CONTENT = ErrorCode(
    code="b1c2d3e4-1111-4101-8101-000000000001",
    msg="Fragment content cannot be empty",
    location="fragment_insert"
)

FRAGMENT_INSERT_UNAUTHORIZED = ErrorCode(
    code="b1c2d3e4-1111-4101-8101-000000000003",
    msg="You are not authorized to insert fragments",
    location="fragment_insert"
)

FRAGMENT_INSERT_EMBEDDING_FAILED = ErrorCode(
    code="b1c2d3e4-1111-4101-8101-000000000004",
    msg="Failed to generate embedding vector for fragment content",
    location="fragment_insert"
)

FRAGMENT_INSERT_RBAC_MISSING = ErrorCode(
    code="b1c2d3e4-1111-4101-8101-000000000005",
    msg="RBAC object not found or access denied",
    location="fragment_insert"
)

FRAGMENT_UPDATE_STALE_DATA = ErrorCode(
    code="b1c2d3e4-2222-4102-8102-000000000012",
    msg="Fragment was modified by another user. Please refresh and try again.",
    location="fragment_update"
)

FRAGMENT_UPDATE_UNAUTHORIZED = ErrorCode(
    code="b1c2d3e4-2222-4102-8102-000000000013",
    msg="You are not authorized to update this fragment",
    location="fragment_update"
)

FRAGMENT_UPDATE_EMBEDDING_FAILED = ErrorCode(
    code="b1c2d3e4-2222-4102-8102-000000000014",
    msg="Failed to update embedding vector for fragment content",
    location="fragment_update"
)

FRAGMENT_DELETE_NOT_FOUND = ErrorCode(
    code="b1c2d3e4-3333-4103-8103-000000000021",
    msg="Fragment not found",
    location="fragment_delete"
)

FRAGMENT_DELETE_UNAUTHORIZED = ErrorCode(
    code="b1c2d3e4-3333-4103-8103-000000000022",
    msg="You are not authorized to delete this fragment",
    location="fragment_delete"
)


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_all_error_codes() -> typing.Dict[str, ErrorCode]:
    """
    Vrátí slovník všech definovaných chybových kódů.
    
    Returns:
        Dict[code: UUID, ErrorCode]: Slovník kde klíč je UUID a hodnota je ErrorCode
    """
    import inspect
    
    error_codes = {}
    for name, obj in globals().items():
        if isinstance(obj, ErrorCode):
            error_codes[obj.code] = obj
    
    return error_codes


def validate_unique_codes() -> bool:
    """
    Ověří, že všechny chybové kódy jsou unikátní.
    
    Raises:
        ValueError: Pokud jsou nalezeny duplicitní kódy
    
    Returns:
        bool: True pokud jsou všechny kódy unikátní
    """
    codes = get_all_error_codes()
    code_list = list(codes.keys())
    
    if len(code_list) != len(set(code_list)):
        # Najdi duplicity
        seen = set()
        duplicates = set()
        for code in code_list:
            if code in seen:
                duplicates.add(code)
            seen.add(code)
        
        raise ValueError(f"Duplicate error codes found: {duplicates}")
    
    return True


def print_error_codes_table():
    """
    Vytiskne tabulku všech chybových kódů pro dokumentaci.
    """
    codes = get_all_error_codes()
    
    print("\n" + "="*100)
    print("ERROR CODES DICTIONARY")
    print("="*100)
    print(f"{'Code (UUID)':<45} {'Location':<35} {'Message':<50}")
    print("-"*100)
    
    for code, error_code in sorted(codes.items()):
        print(f"{error_code.code:<45} {error_code.location:<35} {error_code.msg:<50}")
    
    print("="*100)
    print(f"Total error codes defined: {len(codes)}\n")


# Validace při importu modulu
if __name__ == "__main__":
    # Ověř že všechny kódy jsou unikátní
    try:
        validate_unique_codes()
        print("✓ All error codes are unique")
        print_error_codes_table()
    except ValueError as e:
        print(f"✗ Error code validation failed: {e}")
