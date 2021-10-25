import codecs
import json
import os
from tempfile import TemporaryDirectory
from typing import *

import click
import ffmpeg
from PIL import Image, ImageFont, ImageDraw, ImageEnhance, ImageChops, ImageFilter

from photo_tool.utils import *


def make_shadow(im: Image,
                offset: Tuple[int, int],
                shadow_color,
                blur_radius: float) -> Image:
    shadow_im = Image.new('RGBA', im.size, tuple(int(v * 255) for v in shadow_color))
    shadow_im.putalpha(im.split()[3].point(lambda i: int(i * shadow_color[3])))
    shadow_im = ImageChops.offset(shadow_im, int(offset[0]), int(offset[1]))
    shadow_im = shadow_im.filter(ImageFilter.GaussianBlur(blur_radius))
    return shadow_im


def add_watermark(input_image: Image,
                  text: str,
                  position: str,
                  font_file: str,
                  font_size: float,
                  opacity: float,
                  line_spacing: float,
                  shadow_offset: float,
                  shadow_blur_radius: float,
                  shadow_color=(0., 0., 0., 1.)) -> Image:
    # parse the argument
    im_w, im_h = input_image.size
    h_pos, v_pos = -1, -1

    for pos in position.split():
        if pos == 'right':
            h_pos = -1
        elif pos == 'left':
            h_pos = 1
        elif pos == 'bottom':
            v_pos = -1
        elif pos == 'top':
            v_pos = 1
        else:
            raise ValueError(f'Unrecognized position: {position!r}')

    # inspect the font and size
    size = 2
    while True:
        font = ImageFont.truetype(font_file, size)
        w, line_height = font.getsize('摄影/后期：@02_yuyuko')
        if line_height > min(*input_image.size) * 0.04 * font_size:
            break
        del font
        size += 2
    margin = line_height
    spacing = line_spacing * margin

    # calculate the bbox of text
    lines = text.split('\n')
    wm_width = wm_height = 0
    for line in lines:
        w, h = font.getsize(line)
        wm_width = max(wm_width, w)
        wm_height = wm_height + h + spacing
    wm_height -= spacing

    # now plot each line
    def plot_lines(im):
        draw = ImageDraw.Draw(im, 'RGBA')
        y = im_h - wm_height - margin if v_pos == -1 else margin
        for line in lines:
            w, h = font.getsize(line)
            x = im_w - w - margin if h_pos == -1 else margin
            draw.text(
                xy=(x, y),
                text=line,
                font=font,
                align='left' if h_pos == 1 else 'right'
            )
            y += h + spacing
        del draw

    wm_image = Image.new('RGBA', input_image.size, (0, 0, 0, 0))
    plot_lines(wm_image)

    # make the drop shadow
    shadow_image = make_shadow(
        wm_image,
        (margin * shadow_offset,) * 2,
        shadow_color=shadow_color,
        blur_radius=shadow_blur_radius * margin,
    )
    wm_image = Image.alpha_composite(shadow_image, wm_image)

    # compose with the original image
    alpha = wm_image.split()[3]
    alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
    wm_image.putalpha(alpha)
    im = Image.composite(wm_image, input_image, wm_image)

    # cleanup and return
    wm_image.close()
    return im


def run_job(input_file, output_file, font_file, quality, options, overwrite):
    input_ext = os.path.splitext(input_file)[-1].lower()
    input_image = output_image = None

    try:

        if input_ext in ('.jpg', '.jpeg', '.png', '.bmp'):
            input_image = Image.open(input_file)
            output_image = add_watermark(input_image, font_file=font_file, **options)
            output_image.save(output_file, quality=quality, optimize=True,
                              progressive=True, subsampling=0)

        elif input_ext in ('.avi', '.m4a', '.mkv', '.mov', '.mp4', '.wmv'):
            # probe size
            probe = ffmpeg.probe(input_file)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            width = int(video_stream['width'])
            height = int(video_stream['height'])

            # generate the watermark png
            input_image = Image.new(mode='RGBA', size=(width, height), color=(255, 255, 255, 0))
            output_image = add_watermark(input_image, font_file=font_file, **options)

            with TemporaryDirectory() as temp_dir:
                png_file = os.path.join(temp_dir, 'watermark.png')
                output_image.save(png_file, format='PNG')

                # now render the video
                ffmpeg.filter([ffmpeg.input(input_file), ffmpeg.input(png_file)], 'overlay', 0, 0). \
                    output(output_file). \
                    run(overwrite_output=overwrite)
    
        else:
            raise IOError(f'Unsupported file extension: {input_ext}')

    finally:
        if input_image is not None:
            input_image.close()
        if output_image is not None:
            output_image.close()


@click.command()
@click.option('-t', '--text', required=False, multiple=True)
@click.option('-p', '--position', default='right bottom')
@click.option('-F', '--font-family', default='字心坊初恋物语, Hiragino Sans GB')
@click.option('-S', '--font-size', type=float, default=1.0)
@click.option('-O', '--opacity', type=float, default=0.75)
@click.option('--line-spacing', type=float, default=0.2)
@click.option('--shadow-offset', type=float, default=0.04)
@click.option('--shadow-blur-radius', type=float, default=0.05)
@click.option('-i', '--input-file', required=False)
@click.option('-o', '--output-file', required=False)
@click.option('-q', '--quality', type=int, default=95)
@click.argument('batch_files', nargs=-1)
def main(text, position, font_family, font_size, opacity, line_spacing,
         shadow_offset, shadow_blur_radius, input_file, output_file, quality,
         batch_files):
    # detect whether or not it's single file or batch file mode
    if batch_files:
        if tuple(batch_files) == ('.',):
            batch_files = os.listdir('.')

        if text or input_file is not None or output_file is not None:
            raise ValueError(f'`--text`, `--input-file` or `--output-file` '
                             f'is not allowed for batch mode.')
        print('Enter batch mode')

        for input_file in batch_files:
            meta_file = f'{input_file}.json'
            if os.path.isfile(meta_file):
                print(f'> Input file: {input_file}')
                with codecs.open(meta_file, 'rb', 'utf-8') as f:
                    options = json.load(f)
                    font_file = get_font(options.pop('font_family'))
                    output_file = options.pop('output_file')
                    quality = options.pop('quality')
                    print(f'Font file: {font_file}')

                    if input_file == output_file:
                        raise IOError('`input_file` == `output_file`, which is not allowed.')
                    run_job(input_file, output_file, font_file, quality, options, overwrite=True)

    else:
        if not text or input_file is None or output_file is None:
            raise ValueError(f'`--text`, `--input-file` or `--output-file` '
                             f'is required for single-file mode.')
        text = '\n'.join(text)
        print(f'> Input file: {input_file}\n  Output file: {output_file}')
        if input_file == output_file:
            raise IOError('`input_file` == `output_file`, which is not allowed.')

        font_file = get_font(font_family)
        print(f'Font file: {font_file}')

        options = {
            'text': text,
            'position': position,
            'font_size': font_size,
            'opacity': opacity,
            'line_spacing': line_spacing,
            'shadow_offset': shadow_offset,
            'shadow_blur_radius': shadow_blur_radius,
        }
        run_job(input_file, output_file, font_file, quality, options, overwrite=False)

        options['font_family'] = font_family
        options['output_file'] = output_file
        options['quality'] = quality
        cnt = json.dumps(options)

        with codecs.open(input_file + '.json', 'wb', 'utf-8') as f:
            f.write(cnt)


if __name__ == '__main__':
    main()
