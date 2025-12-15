#!/usr/bin/env python3
import unicodedata
import json
import sys
from pathlib import Path
from typing import Any, Dict

def update_rbac_ids(data: dict) -> dict:
    """
    Najde klíče 'users' a 'groups' a v jejich prvcích
    nastaví 'rbacobject_id' podle hodnoty klíče 'id'.
    """
    for key in ("users", "groups"):
        items = data.get(key)
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            _id = item.get("id")
            if _id is not None:
                item["rbacobject_id"] = _id

    return data

def remove_diacritics(value: str) -> str:
    """
    Odstraní diakritiku z daného řetězce.
    Př. 'čřžáéíóúůšť' -> 'crzaeiouust'
    """
    # NFD: rozloží znaky na základ + diakritické značky
    normalized = unicodedata.normalize("NFD", value)
    # vynecháme všechny znaky, které jsou diakritická znaménka
    stripped = "".join(
        ch for ch in normalized
        if unicodedata.category(ch) != "Mn"
    )
    # vrátíme zpět do běžné podoby
    return unicodedata.normalize("NFC", stripped)


def normalize_user_emails(data: Dict[str, Any]) -> None:
    """
    Projde pole 'users' a u každého záznamu:
    - pokud má atribut 'email' typu str,
      nahradí ho verzí bez diakritiky.
    """
    users = data.get("users")
    if not isinstance(users, list):
        return

    for user in users:
        if not isinstance(user, dict):
            continue
        email = user.get("email")
        if isinstance(email, str):
            user["email"] = remove_diacritics(email)

    return data

def main():
    # if len(sys.argv) < 2:
    #     print("Použití: python update_rbac_ids.py input.json [output.json]")
    #     sys.exit(1)

    # input_path = Path(sys.argv[1])
    input_path = Path("systemdata.rnd.json")
    # output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path
    output_path = Path("systemdata.changed.json")

    if not input_path.is_file():
        print(f"Soubor '{input_path}' neexistuje.")
        sys.exit(1)

    # Načtení JSON
    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Úprava dat
    data = update_rbac_ids(data)
    data = normalize_user_emails(data)

    # Zápis JSON (hezké formátování)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Hotovo. Uloženo do: {output_path}")


if __name__ == "__main__":
    main()
