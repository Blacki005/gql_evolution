# Deníček vývoje: GraphQL Evolution

## Časová osa vývoje

### 📅 20. listopadu 2025 - Základy fragmentů
**Commit:** `548bc23` - *Vytvořené DB model a GQL model pro fragment dokumentu*

První kroky projektu. Vytvořil jsem základní strukturu pro fragmenty dokumentů:
- `FragmentDBModel` - SQLAlchemy model pro ukládání fragmentů
- `FragmentGQLModel` - GraphQL typ pro API

Průběh byl bez závad, základní architektura fungovala na první pokus.

---

### 📅 24. listopadu 2025 - Integrace txtai a embedding vektorů
**Commit:** `e3b23de` - *Mutace pro fragmenty fungují*

Klíčový milník - integrace **txtai** knihovny pro generování embedding vektorů z textu.

#### Co fungovalo:
- Import txtai z Hugging Face
- Model `all-MiniLM-L6-v2` úspěšně generuje embedding vektory
- Mutace pro fragmenty fungují

#### 🔴 Problém #1: Lokální model
Model byl stažený a spouštěl se z lokální podsložky projektu (`/home/filip/all-MiniLM-L6-v2`). To znamenalo, že:
- V Docker kontejneru by import nefungoval
- Model není součástí repozitáře (příliš velký)

> **Poznámka:** Tento problém byl vyřešen později úpravou cest a správným nastavením Docker image.

---

### 📅 30. listopadu 2025 - Dokumenty
**Commit:** `abb0585` - *Přidán DocumentDBModel a DocumentGQLModel*

Rozšíření systému o správu celých dokumentů:
- Dokument může obsahovat více fragmentů
- Fragmenty jsou automaticky generovány z obsahu dokumentu
- Vazba dokument → fragmenty přes `document_id`

---

### 📅 1. prosince 2025 - Přechod na pgvector
**Commity:** `6c713f0`, `62b78a9`

#### 🔴 Problém #2: Meilisearch vs pgvector

Původně jsem zvažoval použití **Meilisearch** pro vektorové vyhledávání. Po analýze jsem se rozhodl pro **pgvector** z následujících důvodů:

| Meilisearch | pgvector |
|-------------|----------|
| Samostatná služba | Rozšíření PostgreSQL |
| Další závislost | Integrováno do DB |
| Složitější nasazení | Jednodušší architektura |

#### Implementace:
1. Nainstalován balíček `postgresql-17-pgvector` na server `postgres-gql-1`
2. Upraven `FragmentDBModel` pro ukládání vektorů pomocí pgvector
3. Upravena inicializační data pro dimenzi 384 (odpovídá `all-MiniLM-L6-v2`)

#### Sémantické vyhledávání:
Implementováno vyhledávání pomocí **kosinové vzdálenosti** mezi embedding vektory:
```python
# pgvector operátor pro kosinovou vzdálenost
FragmentModel.vector.cosine_distance(search_vector) <= threshold
```

---

### 📅 1. prosince 2025 - Oprava UNSET hodnot
**Commit:** `90a5f87`

#### 🔴 Problém #3: Strawberry UNSET vs None

Při edit mutacích se hodnoty, které uživatel nezadal (`UNSET`), přepisovaly na `null/None`. To způsobovalo nechtěné mazání dat.

#### Řešení:
Použití `strawberry.UNSET` pro rozlišení mezi:
- Hodnota nebyla zadána → ponechat původní
- Hodnota byla explicitně nastavena na `None` → nastavit null

```python
if fragment.content is not strawberry.UNSET and fragment.content:
    # Aktualizovat pouze pokud byla hodnota explicitně zadána
    ...
```

---

### 📅 15. prosince 2025 - Test client
**Commit:** `19719d6` - *Přidán test client*

Vytvořen testovací klient schopný automaticky spouštět GraphQL mutace. Základ pro budoucí automatizované testování.

---

### 📅 23. prosince 2025 - Synchronní vs asynchronní generace
**Commit:** `1a3ddc0` - *Implementace synchronní a asynchronní generace fragmentů*

#### 🔴 Problém #4: Testování asynchronní generace

Při vložení dokumentu se fragmenty generují **asynchronně** na pozadí (aby uživatel nečekal). To ale způsobovalo problémy při testování:
- Test vytvořil dokument
- Test ihned kontroloval fragmenty
- Fragmenty ještě nebyly vygenerovány → test selhal

#### Řešení:
Implementace dvou režimů pomocí environment proměnné `SYNC_FRAGMENT_GENERATION`:
- `False` (výchozí) - asynchronní generace pro produkci
- `True` - synchronní generace pro testy

```python
if os.environ.get("SYNC_FRAGMENT_GENERATION", "False").lower() == "true":
    # Čekat na dokončení generace fragmentů
    await generate_document_fragments(...)
else:
    # Spustit na pozadí
    asyncio.create_task(generate_document_fragments(...))
```

---

### 📅 11. ledna 2026 - Autorizace a error handling
**Commity:** `d9fdf98`, `5d94fdb`

#### Autorizace:
- Implementována plná autorizace uživatelů
- Uživatel se může přihlásit jako různé role (nejen superadmin Zdenka Šímečková)
- Různé role mají různá oprávnění (administrátor, děkan, rektor)

#### Centralizované error kódy:
Vytvořen soubor `error_codes.py` s jednotnými chybovými kódy:
```python
DOCUMENT_INSERT_NO_CONTENT = ErrorCode(
    code="a1b2c3d4-1111-4001-8001-000000000001",
    msg="Document content cannot be empty",
    location="Document_insert"
)
```

Přidán **pgvector do docker-compose** pro snadnější nasazení.

---

### 📅 31. ledna 2026 - Refaktoring a CI/CD
**Commity:** `cb3966d`, `4450b84`

#### Odstranění mrtvého kódu:
Analýza ukázala, že některé validace v mutacích jsou **mrtvý kód** - nikdy se nespustí, protože `LoadDataExtension` vrací chybu dříve:

```python
# Tento kód se nikdy nespustí - LoadDataExtension již vrátil chybu
if db_row is None:
    return DeleteError[DocumentGQLModel](...)
```

Mrtvý kód byl odstraněn pro lepší čitelnost a přesnější coverage report.

#### 🔴 Problém #5: pytest-cov a HTTP server

Testy používají HTTP klienta pro komunikaci s GraphQL serverem běžícím v **jiném procesu**. pytest-cov sleduje pouze kód v testovacím procesu, ne v serveru.

**Důsledek:** Coverage report ukazuje ~60% i když je kód reálně testovaný.

**Možná řešení:**
1. Refaktorovat testy na in-process testování s `httpx.ASGITransport`
2. Použít subprocess coverage tracking
3. Akceptovat nižší coverage s dokumentací

#### GitHub Actions workflow:
Přidán workflow pro automatické publikování Docker image:
- Trigger: release nebo manual dispatch
- Build a push na Docker Hub
- Podpora verzování tagů

---

## Shrnutí problémů a jejich řešení

| Problém | Řešení |
|---------|--------|
| Lokální AI model | Správné cesty v Dockerfile |
| Meilisearch komplexita | Přechod na pgvector |
| UNSET vs None | strawberry.UNSET |
| Asynchronní testy | SYNC_FRAGMENT_GENERATION env |
| Coverage tracking | Dokumentace limitace |

---

## Použité technologie

- **Backend:** FastAPI + Strawberry GraphQL (Federation)
- **Databáze:** PostgreSQL + pgvector
- **AI/ML:** txtai + all-MiniLM-L6-v2
- **Testování:** pytest + pytest-asyncio
- **CI/CD:** GitHub Actions + Docker Hub

---

## Závěr

Projekt úspěšně implementuje:
- ✅ CRUD operace pro dokumenty a fragmenty
- ✅ Automatická fragmentace dokumentů
- ✅ Sémantické vyhledávání pomocí vektorových embeddingů
- ✅ Autorizace a oprávnění
- ✅ CI/CD pipeline pro Docker

Hlavní výzvou zůstává správné měření code coverage při integračních testech přes HTTP.

---

*Poslední aktualizace: 1. února 2026*
