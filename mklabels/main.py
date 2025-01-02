from . import pango_cairo
import cairocffi
from dataclasses import dataclass
import warnings
import math

pt_per_mm = 72 / 25.4


def parse_distance(dist_str):
    units = [
        ("mm", pt_per_mm),
        ("pt", 1.0),
        ("", pt_per_mm),
    ]

    for unit, scale in units:
        if dist_str.endswith(unit):
            num = float(dist_str[: len(dist_str) - len(unit)])
            return num * scale

    raise ValueError(f"cannot parse distance {dist_str!r}")


@dataclass
class Margins:
    top: float
    right: float
    bottom: float
    left: float


def parse_margin(margin_str):
    parts = [parse_distance(part) for part in margin_str.split(" ")]

    match parts:
        case [m]:
            return Margins(m, m, m, m)
        case [t, r, b, l]:
            return Margins(t, r, b, l)
        case [t, lr, b]:
            return Margins(t, lr, b, lr)
        case [tb, lr]:
            return Margins(tb, lr, tb, lr)

    raise ValueError(f"cannot parse margins {margin_str!r}")


def parse_args():
    import argparse
    import shlex

    class MyArgumentParser(argparse.ArgumentParser):
        def convert_arg_line_to_args(self, arg_line):
            return shlex.split(arg_line, comments=True)

    parser = MyArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        fromfile_prefix_chars="@",
    )

    add_arg = parser.add_argument

    def add_dist_arg(name, default=None, **kwargs):
        add_arg(name, default=default, type=parse_distance, **kwargs)

    add_arg(
        "--margin", default="0.5mm", type=parse_margin, help="margins in CSS format"
    )
    add_arg("--scale", action="store_true", help="scale text to fit")

    add_arg("--rotate", action="store_true", help="rotate output 90 degrees")

    add_arg("--font", default="sans 10", help="pango font spec")

    # vertical
    add_dist_arg("--label-height", "12mm", help="height of label tape")

    add_arg(
        "--v-align",
        default="center",
        choices=["top", "center", "bottom"],
        help="vertical alignment",
    )

    # horizontal

    add_dist_arg("--label-width", help="fixed label width")

    add_dist_arg("--margin-start", default="0", help="additional margin at start")
    add_dist_arg("--margin-end", default="0", help="additional margin at end")
    add_dist_arg("--margin-inner", default="0", help="additional margin between labels")

    add_arg(
        "--h-align",
        default="center",
        choices=["left", "center", "right"],
        help="horizontal alignment",
    )

    add_arg("in_file", type=argparse.FileType("r"), help="label text input")
    add_arg("out_file", type=argparse.FileType("wb"), help="PDF output")

    return parser.parse_args()


def parse_labels(in_file):
    content = in_file.read()
    pars = content.split("\n\n")

    return [par_strip for par in pars if (par_strip := par.strip())]


def do_layout(context, args, layouts, draw):
    """lay out the labels; if draw is True, actually do the drawing, otherwise
    just apply the transforms

    this leaves the context transformed so that (0, 0) is at the bottom right
    of the label; this is used to calculate the total size before drawing for
    real
    """

    context.translate(args.margin_start, args.margin.top)

    for i, layout in enumerate(layouts):
        if i > 0:
            context.translate(args.margin_inner, 0)

        context.translate(args.margin.left, 0)

        # get the size of the text and the space to put it (label size minus
        # margins)
        extent = pango_cairo.get_logical_extent(layout)
        text_width, text_height = extent.width, extent.height

        space_height = args.label_height - args.margin.top - args.margin.bottom
        space_width = (
            args.label_width - args.margin.left - args.margin.right
            if args.label_width is not None
            else None
        )

        # calculate scale
        if args.scale:
            scale_height = space_height / text_height

            if space_width is not None:
                scale_width = space_width / text_width
                scale = min(scale_height, scale_width)
            else:
                scale = scale_height
        else:
            scale = 1.0

        # check if it fits
        if space_width is not None:
            if text_width * scale > space_width + 1e-6:
                warnings.warn(f"label {i} wider than space width")
        if text_height * scale > space_height + 1e-6:
            warnings.warn(f"label {i} taller than space height")

        # draw and skip over space/text
        if draw:
            with context:
                # align horizontally
                if space_width is not None:
                    h_gap = space_width - text_width * scale
                    left_gap = dict(
                        left=0.0,
                        center=h_gap / 2,
                        right=h_gap,
                    )[args.h_align]

                    context.translate(left_gap, 0)

                # align vertically
                v_gap = space_height - text_height * scale
                top_gap = dict(
                    top=0.0,
                    center=v_gap / 2,
                    bottom=v_gap,
                )[args.v_align]
                context.translate(0, top_gap)

                context.scale(scale)
                # when pango width is set and alignment is right, text is
                # aligned to width, but we deal with that ourselves (to make
                # scale work), so undo it
                context.translate(-extent.x, -extent.y)
                pango_cairo.show_layout(context, layout)
        if space_width is not None:
            context.translate(space_width, 0)
        else:
            context.translate(text_width * scale, 0)

        context.translate(args.margin.right, 0)

    context.translate(args.margin_end, args.label_height - args.margin.top)


alignments = dict(
    left=pango_cairo.ALIGN_LEFT,
    center=pango_cairo.ALIGN_CENTER,
    right=pango_cairo.ALIGN_RIGHT,
)


def run(args):
    surface = cairocffi.PDFSurface(args.out_file, 100.0, 100.0)
    context = cairocffi.Context(surface)

    labels = parse_labels(args.in_file)

    layouts = []
    for label_text in labels:
        label_text = f'<span font="{args.font}">{label_text}</span>'

        layout = pango_cairo.create_layout(context)
        pango_cairo.set_alignment(layout, alignments[args.h_align])

        if args.label_width is not None:
            pango_cairo.set_width(
                layout, args.label_width - args.margin.left - args.margin.right
            )
        pango_cairo.set_markup(layout, label_text)

        layouts.append(layout)

    with context:
        do_layout(context, args, layouts, draw=False)
        width, height = context.get_matrix().transform_point(0, 0)

    if args.rotate:
        width, height = height, width

    surface.set_size(width, height)

    if args.rotate:
        context.rotate(math.pi / 2)
        context.translate(0, -width)

    do_layout(context, args, layouts, draw=True)

    def float_fmt(f):
        return f"{f:.2f}".rstrip("0").rstrip(".")

    width_fmt, height_fmt = float_fmt(width / pt_per_mm), float_fmt(height / pt_per_mm)
    media = f"Custom.{width_fmt}x{height_fmt}mm"
    print("print with:")
    print(f"lp -d label -o media={media} {args.out_file.name}")


def main():
    run(parse_args())


if __name__ == "__main__":
    main()
