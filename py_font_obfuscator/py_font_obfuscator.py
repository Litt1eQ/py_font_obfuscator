import random
import re
import string
from collections import OrderedDict
from pathlib import Path

import emoji
from fontTools import subset
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont


def _get_project_root() -> Path:
    return Path(__file__).parent.parent


class FontNameTable:

    def __init__(self, family_name='CustomAwesomeFont', style_name='Regular', **kwargs):
        """
        see setupNameTable
        @param family_name:
        @param style_name:
        @param kwargs:
        """
        self.family_name = family_name
        self.style_name = style_name
        self.kwargs = kwargs

    def get_name_strings(self):
        return {
            'familyName': self.family_name,
            'styleName': self.style_name,
            'psName': self.family_name + '-' + self.style_name,
            **self.kwargs,
        }


def _pre_deal_obfuscator_input_str(s: str) -> str:
    """
    Pre Deal Input Strings, to deduplicate string & remove all whitespace & remove emoji.
    @param s:
    @return:
    """
    s = "".join(OrderedDict.fromkeys(s))
    s = emoji.demojize(s)
    pattern = re.compile(r'\s+')
    return re.sub(pattern, '', s)


def _check_str_include_emoji(s: str) -> bool:
    for character in s:
        if character in emoji.UNICODE_EMOJI:
            return True
    return False


def _check_cmap_include_all_text(cmap: dict, s: str) -> bool:
    for character in s:
        if ord(character) not in cmap:
            raise Exception(f'{character} Not in Font Lib!')
    return True


def _subset_ttf_font(filepath: str) -> dict:
    options = subset.Options()
    font = subset.load_font(f'{filepath}.ttf', options)
    options.flavor = 'woff'
    subset.save_font(font, f'{filepath}.woff', options)
    options.flavor = 'woff2'
    subset.save_font(font, f'{filepath}.woff2', options)
    return {
        'woff': f'{filepath}.woff',
        'woff2': f'{filepath}.woff2'
    }


def obfuscator(flag=0x0001, plain_text='', shadow_text='', source_font='', output_flag=0x0003, output_file_name='obfuscated_font', output_path='output', name_strings: FontNameTable = None):
    """
    Main Function for Font Obfuscator.
    @param flag: Notice performance issues if you input too many plain text.
        0x0001 Auto Obfuscate Font, You Should Only Input Plain Text.
        0x0002 You should set shadow_text.

        0x0100 This flag will shuffle plain text, you should to notice we if you input shadow text and set this flag, words without correspondence.

        0x1000 Add all numbers to plaintext.
        0x2000 Add all lower letters to plaintext.
        0x4000 Add all upper letters to plaintext.
        0x8000 Add 2, 500 normal characters to plaintext.
    @param plain_text:
    @param shadow_text:
    @param source_font:
    @param output_flag: You could combine flag to output multi files.
        0x0001 .ttf
        0x0002 .woff & .woff2
    @param output_file_name:
    @param output_path:
    @param name_strings:
    @return:
    """

    if flag & 0x1000:
        plain_text += string.digits
    if flag & 0x2000:
        plain_text += string.ascii_lowercase
    if flag & 0x4000:
        plain_text += string.ascii_uppercase
    if flag & 0x8000:
        from py_font_obfuscator.constants import NORMAL_CHINESE_CHARACTERS
        plain_text += NORMAL_CHINESE_CHARACTERS

    plain_text = _pre_deal_obfuscator_input_str(plain_text)
    shadow_text = _pre_deal_obfuscator_input_str(shadow_text)

    if flag & 0x0100:
        plain_text = list(plain_text)
        random.shuffle(plain_text)
        plain_text = ''.join(plain_text)

    if name_strings is None:
        name_strings = FontNameTable()

    _map = {}

    obfuscator_code_list = []

    if flag & 0x0001:
        obfuscator_code_list = random.sample(range(0xE000, 0xF8FF), len(plain_text))
    elif flag & 0x0002:
        if len(shadow_text) < len(plain_text):
            raise Exception('The count of shadow text must greater than plain text!')
        obfuscator_code_list = [ord(i) for i in shadow_text]
    else:
        obfuscator_code_list = random.sample(range(0xE000, 0xF8FF), len(plain_text))

    root = _get_project_root()

    if source_font:
        pass
    else:
        source_font = root / 'base-font/KaiGenGothicCN-Regular.ttf'

    source_font = TTFont(source_font)
    source_cmap = source_font.getBestCmap()

    _check_cmap_include_all_text(source_cmap, plain_text)

    glyphs, metrics, cmap = {}, {}, {}

    glyph_set = source_font.getGlyphSet()
    pen = TTGlyphPen(glyph_set)
    glyph_order = source_font.getGlyphOrder()

    final_shadow_text: list = []

    if 'null' in glyph_order:
        glyph_set['null'].draw(pen)
        glyphs['null'] = pen.glyph()
        metrics['null'] = source_font['hmtx']['null']

        final_shadow_text += ['null']

    if '.notdef' in glyph_order:
        glyph_set['.notdef'].draw(pen)
        glyphs['.notdef'] = pen.glyph()
        metrics['.notdef'] = source_font['hmtx']['.notdef']

        final_shadow_text += ['.notdef']

    for index, character in enumerate(plain_text):
        obfuscator_code = obfuscator_code_list[index]
        code_cmap_name = hex(obfuscator_code).replace('0x', 'uni')
        html_code = hex(obfuscator_code).replace('0x', '&#x') + ';'
        _map[character] = html_code

        final_shadow_text.append(code_cmap_name)
        glyph_set[source_cmap[ord(character)]].draw(pen)
        glyphs[code_cmap_name] = pen.glyph()
        metrics[code_cmap_name] = source_font['hmtx'][source_cmap[ord(character)]]
        cmap[obfuscator_code] = code_cmap_name

    horizontal_header = {
        'ascent': source_font['hhea'].ascent,
        'descent': source_font['hhea'].descent,
    }

    fb = FontBuilder(source_font['head'].unitsPerEm, isTTF=True)
    fb.setupGlyphOrder(final_shadow_text)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(**horizontal_header)
    fb.setupNameTable(name_strings.get_name_strings())
    fb.setupOS2()
    fb.setupPost()

    result = dict()

    if output_flag & 0x0001:
        result['ttf'] = f'./{output_file_name}/{output_file_name}.ttf'
        fb.save(f'./{output_path}/{output_file_name}.ttf')
    if output_flag & 0x0002:
        _subset_ttf_font(f'./{output_path}/{output_file_name}')
    return _map
