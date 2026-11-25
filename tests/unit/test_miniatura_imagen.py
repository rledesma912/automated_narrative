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


def test_a_medio_ver_no_deja_ver_las_formas_del_fondo():
    """Tanda 5 de Peter: el tronco detrás de la figura se veía a través de las piernas."""
    from src.application.services.miniatura import imagen as im_
    from src.application.services.miniatura.arte import arte

    final = Image.new("RGB", (200, 200), (200, 200, 200))
    fondo = Image.new("RGB", (200, 200), (20, 20, 20))
    fondo.paste((240, 240, 240), (95, 0, 105, 200))  # un tronco claro y fino detrás
    alfa = Image.new("L", (200, 200), 0)
    alfa.paste(255, (60, 0, 140, 200))
    out = im_.a_medio_ver(final, fondo, alfa, "mucho", arte())
    tronco, al_lado = out.getpixel((100, 195))[0], out.getpixel((75, 195))[0]
    assert abs(tronco - al_lado) < 15  # sin el borde del tronco: solo el tono


def test_scribble_lineas_blancas_sobre_negro():
    from src.application.services.miniatura import imagen as im_

    boceto = Image.new("RGB", (100, 100), (200, 200, 200))  # papel gris
    boceto.paste((20, 20, 20), (40, 0, 45, 100))  # una línea de lápiz
    s = im_.scribble(boceto)
    assert s.getpixel((10, 10)) == (0, 0, 0)
    assert s.getpixel((42, 50))[0] > 240


def test_detras_se_pega_el_recorte_entero_con_borde_suave():
    """T6.7: el tronco que Qwen pone delante sigue más allá de la silueta de la figura."""
    from src.application.services.miniatura import imagen as im_
    from src.application.services.miniatura.arte import arte

    a = arte()
    gradiente = Image.linear_gradient("L").resize((a.lienzo.ancho, a.lienzo.alto))
    comp = gradiente.point(lambda v: 30 + v // 4).convert("RGB")  # un fondo con variación
    caja = (200, 100, 700, 700)
    m = Image.new("L", comp.size, 0)
    m.paste(255, (400, 300, 500, 600))  # la figura, angosta
    editado = comp.crop(caja)
    editado.paste((200, 200, 200), (100, 0, 160, 600))  # un tronco a la izquierda de la figura
    pegar = im_.mascara_zona(caja, comp.size, a)
    final = im_.pegar_fundido(comp, editado, caja, m, a, pegar)
    fondo = comp.getpixel((330, 400))[0]
    assert final.getpixel((330, 400))[0] > fondo + 60  # el tronco, fuera de la figura, entra
    assert final.getpixel((205, 400)) == comp.getpixel((205, 400))  # el borde no se nota
    assert final.getpixel((100, 400)) == comp.getpixel((100, 400))  # fuera del recorte no toca
    # sin `pegar`, como siempre: solo dentro de la figura
    sin = im_.pegar_fundido(comp, editado, caja, m, a)
    assert sin.getpixel((330, 400)) == comp.getpixel((330, 400))


def test_detras_las_luces_tapadas_no_vuelven():
    from src.application.services.miniatura import imagen as im_

    antes = Image.new("RGB", (60, 60), (20, 20, 20))
    antes.paste((255, 220, 40), (10, 10, 20, 20))  # un ojo
    antes.paste((255, 220, 40), (40, 10, 50, 20))  # el otro
    despues = antes.copy()
    despues.paste((30, 25, 20), (5, 0, 25, 60))  # un tronco tapa el primero
    out = im_.restaurar_luces(antes, despues, solo_visibles=True)
    assert out.getpixel((15, 15))[0] < 60  # el tapado sigue tapado
    assert out.getpixel((45, 15)) == (255, 220, 40)  # el que se ve, con su color


def test_detras_el_recorte_va_de_arriba_a_abajo_sin_borde_en_el_cuadro():
    """Tanda 6: el tronco se cortaba en el borde de arriba del recorte."""
    from src.application.services.miniatura import imagen as im_
    from src.application.services.miniatura.arte import arte

    a = arte()
    m = Image.new("L", (a.lienzo.ancho, a.lienzo.alto), 0)
    m.paste(255, (500, 200, 700, 600))
    caja = im_.zona_detras(m, a)
    assert caja[1] == 0 and caja[3] == a.lienzo.alto
    pegar = im_.mascara_zona(caja, m.size, a)
    assert pegar.getpixel((600, 0)) >= 245 and pegar.getpixel((600, a.lienzo.alto - 1)) >= 245
    assert pegar.getpixel((caja[0] + 1, 300)) < 40  # a los costados sí se difumina


def test_detras_solo_en_las_plantillas_de_arte():
    from src.application.services.miniatura.arte import arte

    assert arte().fundido.detras_en == ["A_der"]  # una sola: las 4 tienen que ser distintas
