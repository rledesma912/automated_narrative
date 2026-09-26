from src.application.services.repetition_check import check

CLICHES = ["me heló la sangre", "un silencio sepulcral"]


def test_frases_repetidas_de_un_acto_anterior():
    acts = [
        "El olor dulce y putrefacto me llenó la nariz. Arranqué el micro.",
        "Otra vez sentí el olor dulce y putrefacto que me llenó la nariz.",
        "Nada que ver con lo anterior, la ruta seguía vacía.",
    ]
    r = check(acts, CLICHES)
    assert r[0].repeated == []
    assert r[1].repeated == [
        "«el olor dulce y putrefacto» (del acto 1)",  # el acto 2 mete «que» en el medio
        "«me llenó la nariz» (del acto 1)",
    ]
    assert r[2].repeated == []


def test_palabras_vacias_no_cuentan():
    r = check(["y de la que se fue", "y de la que se fue"], CLICHES)
    assert r[1].repeated == []


def test_cliches_por_lema():
    r = check(
        ["Aquello me había helado la sangre.", "Hubo un silencio sepulcral.", "Nada."], CLICHES
    )
    assert r[0].cliches == ["me heló la sangre"]
    assert r[1].cliches == ["un silencio sepulcral"]
    assert r[2].cliches == []


def test_raices_no_demasiado_laxas():
    r = check(["La helada del campo, la sangre del animal."], CLICHES)
    assert r[0].cliches == []  # «helada … la sangre» con 3 palabras en el medio no es el cliché


def test_palabras_cortas_no_son_raices():
    r = check(["Como si se fuera un peso de encima.", "Si se calla, el pedido era claro."], CLICHES)
    assert [a.cliches for a in r] == [[], []]  # «si … se» no es «silencio sepulcral»


def test_nombres_inventados():
    known = "José Chofer de micros. El sereno. Villa Esperanza. La mujer del pedestal."
    acts = [
        "Llegué a Villa Esperanza. Mirá, un compañero, Ramón, me dijo que era Laura.",
        "José frenó. Nadie. Después vi el cartel de Villa Esperanza.",
    ]
    r = check(acts, [], known=known)
    assert r[0].invented_names == ["Ramón", "Laura"]
    assert r[1].invented_names == []  # «Nadie» y «Después» arrancan frase


def test_nombres_compuestos_juntos():
    r = check(["Llegué a la entrada de Villa Escondida, de noche."], [], known="José")
    assert r[0].invented_names == ["Villa Escondida"]


def test_rezos_no_son_nombres_inventados():
    r = check(["Recé un Padrenuestro y le pedí a Dios, al Señor, a la Virgen."], [], known="Irene")
    assert r[0].invented_names == []
