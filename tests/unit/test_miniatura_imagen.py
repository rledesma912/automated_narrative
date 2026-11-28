"""Spec-790: lo que hace Python con las imágenes (arte, color, fundido, apoyo)."""

from PIL import Image, ImageDraw

from src.application.services.miniatura import imagen as im_
from src.application.services.miniatura.arte import arte


def _color(w=320, h=180, rgb=(30, 120, 140)) -> Image.Image:
    return Image.new("RGB", (w, h), rgb)


def test_arte_tiene_las_4_plantillas_y_los_tonos():
    a = arte()
    assert list(a.plantillas) == ["A_der", "A_izq", "C_primer_plano", "B_lugar"]  # D21
    assert {"gris_azul", "verde", "azul", "gris_frio", "halloween"} <= set(a.tonos)


def test_el_tono_sale_del_lugar():  # D25
    a = arte()
    assert a.tono_del_lugar("Un bosque de pinos y una torre") == "gris_azul"  # Spec-820 D4
    assert a.tono_del_lugar("Un campo con un maizal") == "verde"
    assert a.tono_del_lugar("El muelle del puerto, de noche") == "azul"
    assert a.tono_del_lugar("Una casa vieja en un pueblo") == a.tono_por_defecto
    assert (
        a.tono_del_lugar("Una mansión en el bosque. Es Halloween.") == "halloween"
    )  # la excepción gana
    assert a.tono_valido("halloween", "bosque") == "halloween"  # lo elegido manda
    assert a.tono_valido("no_existe", "mar") == "azul"


def test_blanco_y_negro_y_desaturado():
    a = arte()
    im, alfa = _color(), Image.new("L", (320, 180), 0)
    byn = im_.colorear(im, alfa, "byn", "verde", a)
    r, g, b = byn.split()
    assert r.tobytes() == g.tobytes() == b.tobytes()
    assert im_.saturacion(im_.desaturar(im, 40)) <= 41


def test_desaturar_respeta_los_acentos_calidos():
    im = _color()
    ImageDraw.Draw(im).rectangle((10, 10, 60, 60), fill=(255, 110, 10))  # la calabaza
    out = im_.desaturar(im, 20)
    assert out.getpixel((35, 35))[0] > 200 and out.getpixel((35, 35))[2] < 60


def test_apoyo_detecta_si_pisa_el_piso_o_va_cortada():
    parada = Image.new("RGBA", (200, 400), (0, 0, 0, 0))
    d = ImageDraw.Draw(parada)
    d.rectangle((90, 0, 110, 380), fill=(255, 255, 255, 255))
    d.rectangle((60, 380, 75, 399), fill=(255, 255, 255, 255))
    d.rectangle((125, 380, 140, 399), fill=(255, 255, 255, 255))
    cortada = Image.new("RGBA", (200, 400), (0, 0, 0, 0))
    ImageDraw.Draw(cortada).rectangle((20, 0, 180, 399), fill=(255, 255, 255, 255))
    assert im_.apoyo(parada) == "piso"
    assert im_.apoyo(cortada) == "borde"


def test_la_foto_del_escenario_se_pide_en_positivo():
    """D27: con cfg 1 nombrar algo con «no» lo trae (E11c: ventanas y casas)."""
    import re

    from src.application.services.miniatura.arte import texto

    plantilla = texto("fotografiar_escenario", descripcion="")
    assert not re.search(r"\b(no|not|without|nobody|never)\b", plantilla, re.I), plantilla


def test_scribble_lineas_blancas_sobre_negro():
    from src.application.services.miniatura import imagen as im_

    boceto = Image.new("RGB", (100, 100), (200, 200, 200))  # papel gris
    boceto.paste((20, 20, 20), (40, 0, 45, 100))  # una línea de lápiz
    s = im_.scribble(boceto)
    assert s.getpixel((10, 10)) == (0, 0, 0)
    assert s.getpixel((42, 50))[0] > 240


def test_detras_solo_en_las_plantillas_de_arte():
    from src.application.services.miniatura.arte import arte

    assert arte().fundido.detras_en == ["A_der"]  # una sola: las 4 tienen que ser distintas


# ── Spec-820: la luz de Yael ──────────────────────────────────────────────────────
def _figura_en_cuadro(a):
    alfa = Image.new("L", (a.lienzo.ancho, a.lienzo.alto), 0)
    ImageDraw.Draw(alfa).rectangle((700, 150, 1000, 700), fill=255)
    return alfa


def test_los_modos_salen_de_la_plantilla():  # D3
    a = arte()
    assert a.plantillas["A_der"].modo == a.plantillas["A_izq"].modo == "respeta"
    assert a.plantillas["C_primer_plano"].modo == a.plantillas["B_lugar"].modo == "reinterpreta"
    assert a.foto("A_der") == (a.modos["respeta"].cambio, a.modos["respeta"].fuerza)
    assert a.foto("B_lugar")[1] == a.plantillas["B_lugar"].fuerza  # la de la plantilla manda


def test_un_modo_que_no_existe_no_carga():
    import pytest

    from src.application.services.miniatura.arte import Arte

    datos = arte().model_dump()
    datos["plantillas"]["A_der"]["modo"] = "otro"
    with pytest.raises(ValueError):
        Arte.model_validate(datos)


def test_iluminar_el_fondo_aclara_lo_lejano_y_deja_oscuro_lo_cercano():
    a = arte()
    fondo = Image.new("RGB", (a.lienzo.ancho, a.lienzo.alto), (20, 20, 20))
    fondo.paste((110, 110, 110), (0, 0, 640, 300))  # niebla tenue arriba a la izquierda
    out = im_.iluminar_fondo(fondo, a)
    assert out.getpixel((300, 120))[0] > 150  # la niebla, clara
    assert out.getpixel((1000, 600))[0] < 40  # lo oscuro sigue oscuro


def test_la_composicion_pone_la_figura_en_silueta_con_halo_y_ojos():
    a = arte()
    fondo = Image.new("RGB", (a.lienzo.ancho, a.lienzo.alto), (60, 60, 60))
    f = Image.new("RGBA", (300, 550), (180, 180, 180, 255))
    ImageDraw.Draw(f).rectangle((200, 60, 230, 90), fill=(255, 230, 60, 255))  # un ojo
    alfa = im_.alfa_en_cuadro(f, (700, 150), a)
    comp = im_.componer_con_luz(fondo, f, (700, 150), alfa, a)
    assert comp.getpixel((750, 500))[0] <= a.luz.silueta_techo  # la figura, oscura
    junto = 1000 + round(a.luz.halo.radio * a.lienzo.alto / 3)
    assert comp.getpixel((junto, 400))[0] > 100  # el halo, pegado a la figura y tenue
    assert comp.getpixel((1000 + round(a.luz.halo.radio * a.lienzo.alto * 3), 400))[0] < 75
    r, g, b = comp.getpixel((915, 225))
    assert r > 200 and b < 120  # el ojo, amarillo


def test_la_guia_pone_la_figura_cerca_el_halo_lejos_y_el_tronco_mas_cerca():
    a = arte()
    alfa = _figura_en_cuadro(a)
    comp = Image.new("RGB", alfa.size, (30, 30, 30))
    sin = im_.profundidad(comp, alfa, a)
    assert sin.getpixel((850, 400))[0] == 255  # la figura, cerca
    junto = 1000 + round(a.luz.profundidad_anillo * a.lienzo.alto / 3)
    assert sin.getpixel((junto, 400))[0] < 60  # el halo, lejos
    tronco = im_.mascara_tronco(alfa, a)
    con = im_.profundidad(comp, alfa, a, tronco)
    x = round(700 + a.luz.tronco.centro * 300)
    assert con.getpixel((x, 400))[0] == 255 > con.getpixel((960, 400))[0]  # el tronco tapa


def test_el_tronco_va_de_arriba_a_abajo_y_deja_ver_la_cabeza():
    a = arte()
    alfa = _figura_en_cuadro(a)
    t = im_.mascara_tronco(alfa, a)
    x = round(700 + a.luz.tronco.centro * 300)
    assert t.getpixel((x, 0)) > 200 and t.getpixel((x, a.lienzo.alto - 1)) > 200
    assert t.getpixel((990, 200)) == 0  # el costado de la cabeza queda a la vista
    assert im_.mascara_tronco(Image.new("L", alfa.size, 0), a) is None


def test_despegar_aclara_alrededor_y_no_la_figura():
    a = arte()
    foto = Image.new("RGB", (a.lienzo.ancho, a.lienzo.alto), (60, 60, 60))
    figura = _figura_en_cuadro(a)
    out = im_.despegar(foto, figura, a)
    junto = 1000 + round(a.luz.despegar.anillo * a.lienzo.alto / 3)
    assert out.getpixel((junto, 400))[0] > 70  # el anillo
    assert out.getpixel((850, 400)) == (60, 60, 60)  # la figura, igual
    assert out.getpixel((100, 400)) == (60, 60, 60)  # lejos, igual


def test_mate_aplasta_los_reflejos_y_deja_los_ojos():  # D7
    a = arte()
    foto = Image.new("RGB", (a.lienzo.ancho, a.lienzo.alto), (20, 20, 20))
    foto.paste((200, 200, 200), (800, 400, 860, 460))  # un brillo de plástico en el cuerpo
    foto.paste((255, 210, 40), (900, 250, 930, 280))  # un ojo
    out = im_.mate(foto, _figura_en_cuadro(a), a)
    assert out.getpixel((830, 430))[0] < 120
    r, g, b = out.getpixel((915, 265))
    assert r > 230 and b < 80


def test_controlar_y_medir_la_luz():
    a = arte()
    foto = Image.linear_gradient("L").rotate(90).resize((1344, 768)).point(lambda v: 40 + v // 3)
    out = im_.controlar_luz(foto.convert("RGB"), a)
    assert out.size == (a.lienzo.ancho, a.lienzo.alto)
    luz = im_.medir_luz(out)
    assert out.convert("L").getextrema() == (0, 255)  # negro y blanco de verdad
    assert set(luz) == {"media", "p5", "p95"} and luz["p5"] < luz["media"] < luz["p95"]


def test_si_la_foto_apago_los_ojos_vuelven_y_si_no_no_se_toca():
    a = arte()
    figura = _figura_en_cuadro(a)
    comp = Image.new("RGB", figura.size, (20, 20, 20))
    comp.paste((255, 215, 70), (900, 250, 930, 280))  # el ojo de la composición
    apagada = Image.new("RGB", figura.size, (20, 20, 20))
    r, g, b = im_.devolver_ojos(apagada, comp, figura, a).getpixel((915, 265))
    assert r > 200 and b < 120
    con_ojos = apagada.copy()
    con_ojos.paste((255, 210, 40), (850, 250, 870, 270))  # la foto puso los ojos en otro lado
    assert im_.devolver_ojos(con_ojos, comp, figura, a) is con_ojos
    afuera = Image.new("L", figura.size, 0)  # la cabeza ya no está ahí: no se pinta
    assert im_.devolver_ojos(apagada, comp, afuera, a) is apagada


def test_la_corteza_es_oscura_y_con_vetas():
    a = arte()
    alfa = _figura_en_cuadro(a)
    tronco = im_.mascara_tronco(alfa, a)
    out = im_.pegar_tronco(Image.new("RGB", alfa.size, (200, 200, 200)), tronco, 7, a)
    x = round(700 + a.luz.tronco.centro * 300)
    columna = [out.getpixel((x, y))[0] for y in range(0, a.lienzo.alto, 10)]
    assert max(columna) <= a.luz.tronco.oscuro[1] and max(columna) - min(columna) > 20


def test_contar_ojos_nota_una_cabeza_de_mas():  # tanda 18
    im = Image.new("RGB", (1280, 720), (30, 30, 30))
    d = ImageDraw.Draw(im)
    for x in (900, 980):
        d.ellipse((x, 200, x + 30, 230), fill=(255, 210, 40))
    assert im_.contar_ojos(im) == 2
    for x in (200, 280):
        d.ellipse((x, 150, x + 30, 180), fill=(255, 210, 40))
    assert im_.contar_ojos(im) == 4
