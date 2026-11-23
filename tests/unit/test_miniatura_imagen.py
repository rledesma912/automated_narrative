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
    assert a.tono_del_lugar("Una mansión en el bosque. Es Halloween.") == "halloween"  # la excepción gana
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
