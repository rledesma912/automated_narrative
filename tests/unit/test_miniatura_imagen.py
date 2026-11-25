"""Spec-790: lo que hace Python con las imágenes (arte, color, fundido, apoyo)."""

from PIL import Image, ImageChops, ImageDraw

from src.application.services.miniatura import imagen as im_
from src.application.services.miniatura.arte import arte


def _color(w=320, h=180, rgb=(30, 120, 140)) -> Image.Image:
    return Image.new("RGB", (w, h), rgb)


def test_arte_tiene_las_4_plantillas_y_los_tonos():
    a = arte()
    assert list(a.plantillas) == ["A_der", "A_izq", "C_primer_plano", "B_lugar"]  # D21
    assert {"verde", "azul", "gris_frio", "halloween"} <= set(a.tonos)


def test_el_tono_sale_del_lugar():  # D25
    a = arte()
    assert a.tono_del_lugar("Un bosque de pinos y una torre") == "verde"
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


def test_el_fundido_no_toca_nada_fuera_de_la_mascara():
    a = arte()
    comp = Image.effect_noise((a.lienzo.ancho, a.lienzo.alto), 40).convert("RGB")
    alfa = Image.new("L", comp.size, 0)
    ImageDraw.Draw(alfa).ellipse((500, 100, 700, 650), fill=255)
    m = im_.mascara_fundir(alfa, a)
    caja = im_.zona(m, a)
    editado = Image.new("RGB", (caja[2] - caja[0], caja[3] - caja[1]), (250, 250, 250))
    out = im_.pegar_fundido(comp, editado, caja, m, a)
    afuera = ImageChops.invert(m.point(lambda v: 255 if v > 0 else 0))
    dif = ImageChops.difference(out, comp).convert("L")
    assert ImageChops.multiply(dif, afuera).getbbox() is None


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


def test_oscurecer_la_figura_respeta_la_calabaza_encendida():
    a = arte()
    f = Image.new("RGBA", (200, 400), (200, 200, 200, 255))
    ImageDraw.Draw(f).rectangle((60, 200, 140, 280), fill=(255, 120, 20, 255))  # la calabaza
    fondo = Image.new("RGB", (a.lienzo.ancho, a.lienzo.alto), (15, 15, 18))
    alfa = im_.alfa_en_cuadro(f, (500, 200), a)
    out = im_.oscurecer_figura(f, fondo, alfa, a)
    assert out.getpixel((10, 10))[0] < 150  # el cuerpo se oscurece
    r, g, b, _ = out.getpixel((100, 240))
    assert r > 200 and b < 80  # la calabaza sigue encendida


# ── T6.4 y T3.3 ──────────────────────────────────────────────────────────────────
def test_los_ojos_amarillos_sobreviven_al_fundido():
    from src.application.services.miniatura import imagen as im_

    antes = Image.new("RGB", (40, 40), (20, 20, 20))
    antes.paste((230, 190, 40), (10, 10, 20, 20))  # un ojo amarillo que brilla
    despues = Image.new("RGB", (40, 40), (20, 20, 20))
    despues.paste((170, 200, 120), (10, 10, 20, 20))  # el fundido lo dejó verdoso
    r, g, b = im_.restaurar_luces(antes, despues).getpixel((15, 15))
    assert r > g > b  # vuelve a ser amarillo
    assert im_.restaurar_luces(antes, despues).getpixel((35, 35)) == (20, 20, 20)


def test_a_medio_ver_oscurece_abajo_y_no_arriba():
    from src.application.services.miniatura import imagen as im_
    from src.application.services.miniatura.arte import arte

    final = Image.new("RGB", (100, 100), (200, 200, 200))
    fondo = Image.new("RGB", (100, 100), (100, 100, 100))
    alfa = Image.new("L", (100, 100), 0)
    alfa.paste(255, (30, 0, 70, 100))
    out = im_.a_medio_ver(final, fondo, alfa, "mucho", arte())
    assert out.getpixel((50, 5)) == (200, 200, 200)  # la cabeza, igual
    assert out.getpixel((50, 98))[0] < 80  # los pies, en la sombra del lugar
    assert out.getpixel((5, 98)) == (200, 200, 200)  # fuera de la figura no toca
    assert im_.a_medio_ver(final, fondo, alfa, "no", arte()) is final


def test_la_foto_del_escenario_se_pide_en_positivo():
    """D27: con cfg 1 nombrar algo con «no» lo trae (E11c: ventanas y casas)."""
    import re

    from src.application.services.miniatura.arte import texto

    plantilla = texto("fotografiar_escenario", descripcion="")
    assert not re.search(r"\b(no|not|without|nobody|never)\b", plantilla, re.I), plantilla
