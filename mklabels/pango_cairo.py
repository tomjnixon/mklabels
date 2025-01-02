"""minimal cffi interface to pango and pangocairo

adapted from https://doc.courtbouillon.org/cairocffi/stable/cffi_api.html#using-pango
"""

import cffi
from dataclasses import dataclass

ffi = cffi.FFI()
ffi.cdef(
    """
    /* GLib */
    typedef void cairo_t;
    typedef void* gpointer;
    void g_object_unref (gpointer object);

    /* Pango and PangoCairo */
    typedef ... PangoLayout;
    typedef enum {
        PANGO_ALIGN_LEFT,
        PANGO_ALIGN_CENTER,
        PANGO_ALIGN_RIGHT
    } PangoAlignment;
    typedef struct {
        int x;
        int y;
        int width;
        int height;
    } PangoRectangle;
    int pango_units_from_double (double d);
    double pango_units_to_double (int d);
    PangoLayout * pango_cairo_create_layout (cairo_t *cr);
    void pango_cairo_show_layout (cairo_t *cr, PangoLayout *layout);

    void pango_layout_set_width (PangoLayout *layout, int width);
    void pango_layout_set_alignment (
        PangoLayout *layout, PangoAlignment alignment);
    void pango_layout_set_markup (
        PangoLayout *layout, const char *text, int length);
    void pango_layout_get_size (
        PangoLayout* layout,
        int* width,
        int* height);
    void pango_layout_get_extents (
        PangoLayout* layout,
        PangoRectangle* ink_rect,
        PangoRectangle* logical_rect);
        """
)
pangocairo = ffi.dlopen("pangocairo-1.0")
gobject = ffi.dlopen("gobject-2.0")
pango = ffi.dlopen("pango-1.0")


def gobject_ref(pointer):
    return ffi.gc(pointer, gobject.g_object_unref)


ALIGN_LEFT = pango.PANGO_ALIGN_LEFT
ALIGN_CENTER = pango.PANGO_ALIGN_CENTER
ALIGN_RIGHT = pango.PANGO_ALIGN_RIGHT


units_from_double = pango.pango_units_from_double
units_to_double = pango.pango_units_to_double


def create_layout(context):
    return gobject_ref(pangocairo.pango_cairo_create_layout(context._pointer))


def get_size(layout):
    width, height = ffi.new("int *"), ffi.new("int *")
    pango.pango_layout_get_size(layout, width, height)
    return units_to_double(width[0]), units_to_double(height[0])


@dataclass
class Rectangle:
    x: float
    y: float
    width: float
    height: float


def get_logical_extent(layout):
    extent = ffi.new("PangoRectangle *")
    pango.pango_layout_get_extents(layout, ffi.NULL, extent)

    return Rectangle(
        x=units_to_double(extent.x),
        y=units_to_double(extent.y),
        width=units_to_double(extent.width),
        height=units_to_double(extent.height),
    )


def set_markup(layout, markup):
    markup = ffi.new("char[]", markup.encode("utf8"))
    pango.pango_layout_set_markup(layout, markup, -1)


def set_alignment(layout, alignment):
    pango.pango_layout_set_alignment(layout, alignment)


def set_width(layout, width):
    pango.pango_layout_set_width(layout, units_from_double(width))


def show_layout(context, layout):
    pangocairo.pango_cairo_show_layout(context._pointer, layout)
