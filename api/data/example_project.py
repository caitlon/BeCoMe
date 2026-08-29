"""Static content of the example project seeded into every activated account.

The opinions are the Floods case study from the source paper, the same numbers
``examples/data/floods_case.txt`` carries and ``tests/reference/floods_case.py``
pins the expected result to. The accounts holding them are service accounts: the
addresses use ``.invalid`` (RFC 2606), which no mail can ever reach.

Kept as a Python module rather than JSON so mypy checks the shape at build time
instead of the seeding service discovering a malformed record at runtime.
"""

from dataclasses import dataclass
from typing import Final
from uuid import UUID

_CZECH = "cs"


@dataclass(frozen=True, slots=True)
class ExampleExpert:
    """One demo account and the opinion it holds in every example project.

    :ivar user_id: Fixed account id, so the pool is created once and reused.
    :ivar first_name: Given name shown in the project's team table.
    :ivar last_name: Family name shown in the project's team table.
    :ivar email: Undeliverable ``.invalid`` address.
    :ivar position_en: Role shown with the opinion in English.
    :ivar position_cs: Role shown with the opinion in Czech.
    :ivar lower_bound: Pessimistic end of the expert's estimate.
    :ivar peak: The expert's best proposal.
    :ivar upper_bound: Optimistic end of the expert's estimate.
    """

    user_id: UUID
    first_name: str
    last_name: str
    email: str
    position_en: str
    position_cs: str
    lower_bound: float
    peak: float
    upper_bound: float

    def position(self, language: str) -> str:
        """Return the role label for a language, falling back to English.

        :param language: Two-letter UI language code.
        :return: The Czech label for ``cs``, the English one otherwise.
        """
        return self.position_cs if language == _CZECH else self.position_en


@dataclass(frozen=True, slots=True)
class ExampleProjectText:
    """The project's own name and description in one language.

    :ivar name: Project name.
    :ivar description: Project description, including the question being decided.
    """

    name: str
    description: str


EXAMPLE_SCALE_MIN: Final[float] = 0.0
EXAMPLE_SCALE_MAX: Final[float] = 100.0
EXAMPLE_SCALE_UNIT: Final[str] = "%"

EXAMPLE_EXPERTS: Final[tuple[ExampleExpert, ...]] = (
    ExampleExpert(
        user_id=UUID("922f3d9b-20be-461f-9b69-90928701ce93"),
        first_name="Jana",
        last_name="Nováková",
        email="jana.novakova@example.invalid",
        position_en="Hydrologist 1",
        position_cs="Hydrolog 1",
        lower_bound=37.0,
        peak=42.0,
        upper_bound=47.0,
    ),
    ExampleExpert(
        user_id=UUID("2458e540-24e4-46e5-b2cf-6caac4b9c637"),
        first_name="Petr",
        last_name="Svoboda",
        email="petr.svoboda@example.invalid",
        position_en="Hydrologist 2",
        position_cs="Hydrolog 2",
        lower_bound=42.0,
        peak=50.0,
        upper_bound=50.0,
    ),
    ExampleExpert(
        user_id=UUID("a15919aa-5727-4fb9-84e9-2980007cfc58"),
        first_name="Marie",
        last_name="Dvořáková",
        email="marie.dvorakova@example.invalid",
        position_en="Nature Protection Officer",
        position_cs="Pracovník ochrany přírody",
        lower_bound=5.0,
        peak=7.0,
        upper_bound=9.0,
    ),
    ExampleExpert(
        user_id=UUID("7ec7b7c3-126b-412a-babf-fd79d002e921"),
        first_name="Tomáš",
        last_name="Černý",
        email="tomas.cerny@example.invalid",
        position_en="Risk Management Expert",
        position_cs="Expert na řízení rizik",
        lower_bound=37.0,
        peak=40.0,
        upper_bound=48.0,
    ),
    ExampleExpert(
        user_id=UUID("9b8d41e8-ad45-4b7d-a541-38d781be09da"),
        first_name="Lucie",
        last_name="Procházková",
        email="lucie.prochazkova@example.invalid",
        position_en="Land Use Planner",
        position_cs="Územní plánovač",
        lower_bound=6.0,
        peak=8.0,
        upper_bound=11.0,
    ),
    ExampleExpert(
        user_id=UUID("d171a368-ea6a-45f5-9b66-6767052fe916"),
        first_name="Jan",
        last_name="Kučera",
        email="jan.kucera@example.invalid",
        position_en="Civil Service Representative",
        position_cs="Zástupce státní správy",
        lower_bound=5.0,
        peak=8.0,
        upper_bound=9.0,
    ),
    ExampleExpert(
        user_id=UUID("923c3a06-0b09-4573-a4da-142c606ae61e"),
        first_name="Eva",
        last_name="Veselá",
        email="eva.vesela@example.invalid",
        position_en="Municipality 1",
        position_cs="Obec 1",
        lower_bound=33.0,
        peak=38.0,
        upper_bound=43.0,
    ),
    ExampleExpert(
        user_id=UUID("1a530254-57f0-4a8d-adb9-7d5520153f50"),
        first_name="Martin",
        last_name="Horák",
        email="martin.horak@example.invalid",
        position_en="Municipality 2",
        position_cs="Obec 2",
        lower_bound=5.0,
        peak=8.0,
        upper_bound=8.0,
    ),
    ExampleExpert(
        user_id=UUID("d5bb3746-fdf8-424d-ba9d-3d7d407756a9"),
        first_name="Tereza",
        last_name="Němcová",
        email="tereza.nemcova@example.invalid",
        position_en="Economist",
        position_cs="Ekonom",
        lower_bound=10.0,
        peak=14.0,
        upper_bound=20.0,
    ),
    ExampleExpert(
        user_id=UUID("624423f1-04b4-404c-8d55-d1cb82fa8ae4"),
        first_name="Pavel",
        last_name="Marek",
        email="pavel.marek@example.invalid",
        position_en="Rescue Coordinator",
        position_cs="Koordinátor záchranných složek",
        lower_bound=40.0,
        peak=45.0,
        upper_bound=50.0,
    ),
    ExampleExpert(
        user_id=UUID("9f48758c-53ae-4d68-a454-d9c10767104e"),
        first_name="Hana",
        last_name="Pokorná",
        email="hana.pokorna@example.invalid",
        position_en="Land Owner 1",
        position_cs="Vlastník půdy 1",
        lower_bound=2.0,
        peak=3.0,
        upper_bound=4.0,
    ),
    ExampleExpert(
        user_id=UUID("329f1e51-a2ee-4d24-ab04-a7720bf3eac7"),
        first_name="Jiří",
        last_name="Krejčí",
        email="jiri.krejci@example.invalid",
        position_en="Land Owner 2",
        position_cs="Vlastník půdy 2",
        lower_bound=0.0,
        peak=0.0,
        upper_bound=2.0,
    ),
    ExampleExpert(
        user_id=UUID("db3205fc-c11b-431e-950e-573c5bcb4013"),
        first_name="Zuzana",
        last_name="Bláhová",
        email="zuzana.blahova@example.invalid",
        position_en="Land Owner 3",
        position_cs="Vlastník půdy 3",
        lower_bound=0.0,
        peak=2.0,
        upper_bound=3.0,
    ),
)

EXAMPLE_PROJECT_TEXT: Final[dict[str, ExampleProjectText]] = {
    "en": ExampleProjectText(
        name="Flood Prevention Planning",
        description=(
            "Example project. What percentage reduction of arable land in flood "
            "areas is recommended to prevent floods? Thirteen experts from the "
            "published case study have already answered. Add your own opinion to "
            "see how the compromise moves, or delete this project if you do not "
            "need it."
        ),
    ),
    "cs": ExampleProjectText(
        name="Plánování protipovodňové ochrany",
        description=(
            "Ukázkový projekt. Jaké procentuální snížení orné půdy v záplavových "
            "oblastech se doporučuje k prevenci povodní? Třináct expertů z "
            "publikované případové studie již odpovědělo. Přidejte svůj názor a "
            "uvidíte, jak se kompromis posune, nebo projekt smažte, pokud ho "
            "nepotřebujete."
        ),
    ),
}
