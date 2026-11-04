#!/usr/bin/env python3
"""Subset an existing licensed Noto CFF font and convert outlines for embedding."""
from pathlib import Path
import argparse
from fontTools.ttLib import TTFont
from fontTools import subset
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen
ROOT=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('source_font');args=ap.parse_args()
f=TTFont(args.source_font)
notice='\n'.join(str(n.toUnicode()) for n in f['name'].names if n.nameID in [0,13,14])
opt=subset.Options();opt.glyph_names=True
s=subset.Subsetter(options=opt)
s.populate(text=(ROOT/'make_report.py').read_text()+''.join(chr(x) for x in range(32,127)))
s.subset(f)
order=f.getGlyphOrder();gset=f.getGlyphSet();glyf={}
for name in order:
    pen=TTGlyphPen(None);gset[name].draw(Cu2QuPen(pen,max_err=1.,reverse_direction=True));glyf[name]=pen.glyph()
b=FontBuilder(f['head'].unitsPerEm,isTTF=True);b.setupGlyphOrder(order)
b.setupCharacterMap(f.getBestCmap());b.setupGlyf(glyf);b.setupHorizontalMetrics(f['hmtx'].metrics)
b.setupHorizontalHeader(ascent=f['hhea'].ascent,descent=f['hhea'].descent,lineGap=f['hhea'].lineGap)
b.setupNameTable({'familyName':'Report SC Subset','styleName':'Regular',
 'uniqueFontIdentifier':'ReportSCSubset-20261104','fullName':'Report SC Subset Regular',
 'psName':'ReportSCSubset-Regular','copyright':notice})
o=f['OS/2'];b.setupOS2(sTypoAscender=o.sTypoAscender,sTypoDescender=o.sTypoDescender,
 usWinAscent=o.usWinAscent,usWinDescent=o.usWinDescent)
b.setupPost();b.setupMaxp()
assets=ROOT/'assets';assets.mkdir(exist_ok=True)
b.save(assets/'ReportSCSubset-Regular.ttf')
(assets/'FONT_NOTICE.txt').write_text('Derived subset of Noto Sans SC. Original notices:\n'+notice+'\n')
print('Embedded font glyphs:',len(order))
