"""Complete Figure 5A-F from the supplied map and four revised CSV tables.

The map is embedded at its original aspect ratio; sources are never modified.
Run from an environment installed with requirements.txt; Arial is required.
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
import os
import shutil
import sys

WORKSPACE = Path(__file__).resolve().parents[1]
os.environ['MPLCONFIGDIR'] = str(WORKSPACE / 'build' / 'matplotlib_cache')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager, colors, cbook
from matplotlib.patches import Patch
from matplotlib.ticker import FormatStrFormatter
from PIL import Image
from pypdf import PdfReader

SOURCE = WORKSPACE / 'data' / 'figure5'
OUT = WORKSPACE / 'build' / 'figure5'
OUT.mkdir(parents=True, exist_ok=True)
STEM = 'Figure5_Complete_Management_pathways'
MAP_FILE = SOURCE / 'Figure5a_source.tif'
FILES = {
    'area': 'R08_Management_AreaSummary_REVISED.csv',
    'gde': 'R08_Management_ByGDE_REVISED.csv',
    'aridity': 'R08_Management_ByAridity_REVISED.csv',
    'main': 'R08_FinalManagement_ByClass_REVISED.csv',
}
data = {}
for key, name in FILES.items():
    with (SOURCE / name).open(encoding='utf-8-sig', newline='') as f:
        data[key] = list(csv.DictReader(f))

# Matching always uses the original strings, never the shortened display labels.
PATHWAYS = [
    ('Natural sparse/open conservation', 'Sparse/open conservation', '#C9B99A'),
    ('Close-to-nature structural management', 'Close-to-nature management', '#66A69E'),
    ('GDE conservation / passive recovery', 'GDE conservation & recovery', '#4C78A8'),
    ('Low-tree mixed restoration', 'Low-tree mixed restoration', '#228833'),
    ('Herbaceous/exclosure passive recovery', 'Herbaceous recovery', '#E3B34B'),
]
PATHWAY_FIELD = 'FinalManagementPathway'
pathway_names = [p[0] for p in PATHWAYS]
pathway_labels = {p[0]: p[1] for p in PATHWAYS}
pathway_colors = {p[0]: p[2] for p in PATHWAYS}
pathway_order = {p[0]: i + 1 for i, p in enumerate(PATHWAYS)}
required_fields = {
    'area': [PATHWAY_FIELD, 'PathwayOrder', 'Area_km2', 'Area_share_pct', 'n_ClassCode', 'Denominator_Area_km2'],
    'gde': [PATHWAY_FIELD, 'PathwayOrder', 'GDE_Level', 'Area_km2', 'Within_GDE_Level_pct', 'GDE_total_area_km2'],
    'aridity': [PATHWAY_FIELD, 'PathwayOrder', 'AridityClass', 'AridityPlotOrder', 'Area_km2', 'Within_Aridity_pct', 'Aridity_total_area_km2'],
    'main': [PATHWAY_FIELD, 'ClassCode', 'Area_km2', 'GDE_Level', 'AridityClass', 'Figure5_EF_Include', 'LAI_target', 'V_target'],
}
for key, fields in required_fields.items():
    assert data[key], f'Empty file: {key}'
    assert set(fields) <= set(data[key][0]), f'Missing fields in {key}'
    for row in data[key]:
        assert row[PATHWAY_FIELD] in pathway_order
        assert int(row['PathwayOrder']) == pathway_order[row[PATHWAY_FIELD]]

def number(row, key):
    value = float(row[key])
    assert math.isfinite(value), (row.get('ClassCode'), key)
    return value

def close(a, b):
    return math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-7)

main = data['main']
assert len({r['ClassCode'] for r in main}) == len(main), 'Duplicate ClassCode'
area_rows = sorted(data['area'], key=lambda r: int(r['PathwayOrder']))
assert [r[PATHWAY_FIELD] for r in area_rows] == pathway_names
total_area = sum(number(r, 'Area_km2') for r in main)
regional_counts = Counter(r[PATHWAY_FIELD] for r in main)
for r in area_rows:
    observed_area = sum(number(m, 'Area_km2') for m in main if m[PATHWAY_FIELD] == r[PATHWAY_FIELD])
    assert close(number(r, 'Area_km2'), observed_area)
    assert close(number(r, 'Denominator_Area_km2'), total_area)
    assert close(number(r, 'Area_share_pct'), observed_area / total_area * 100)
    assert int(r['n_ClassCode']) == regional_counts[r[PATHWAY_FIELD]]
assert close(sum(number(r, 'Area_share_pct') for r in area_rows), 100)

gde_levels = sorted({int(r['GDE_Level']) for r in data['gde']})
aridity_order_pairs = sorted({(int(r['AridityPlotOrder']), r['AridityClass']) for r in data['aridity']})
assert len({a for _, a in aridity_order_pairs}) == len(aridity_order_pairs)
aridity_classes = [a for _, a in aridity_order_pairs]
def validate_group_table(key, group_field, groups, percent_field, denominator_field):
    rows = data[key]
    assert len(rows) == len(groups) * len(PATHWAYS), f'Incomplete group/pathway grid: {key}'
    lookup = {(r[group_field], r[PATHWAY_FIELD]): r for r in rows}
    assert len(lookup) == len(rows), f'Duplicate group/pathway keys: {key}'
    matrix = []
    for group in groups:
        group_rows = [m for m in main if m[group_field] == str(group)]
        denom = sum(number(m, 'Area_km2') for m in group_rows)
        assert denom > 0
        percentages = []
        for pathway in pathway_names:
            r = lookup[(str(group), pathway)]
            actual = sum(number(m, 'Area_km2') for m in group_rows if m[PATHWAY_FIELD] == pathway)
            assert close(number(r, 'Area_km2'), actual)
            assert close(number(r, denominator_field), denom)
            assert close(number(r, percent_field), actual / denom * 100)
            assert int(r['n_ClassCode']) == sum(m[PATHWAY_FIELD] == pathway for m in group_rows)
            percentages.append(number(r, percent_field))
        assert close(sum(percentages), 100)
        matrix.append(percentages)
    return np.array(matrix)

gde_matrix = validate_group_table('gde', 'GDE_Level', gde_levels, 'Within_GDE_Level_pct', 'GDE_total_area_km2')
aridity_matrix = validate_group_table('aridity', 'AridityClass', aridity_classes, 'Within_Aridity_pct', 'Aridity_total_area_km2')
selected = sorted([r for r in main if int(r['Figure5_EF_Include']) == 1], key=lambda r: int(r['ClassCode']))
unselected = [r for r in main if int(r['Figure5_EF_Include']) != 1]
ef_pathways = [PATHWAYS[i][0] for i in (1, 3)]
assert set(r[PATHWAY_FIELD] for r in selected) == set(ef_pathways)
assert all(not r['LAI_target'] and not r['V_target'] for r in unselected)
groups = {p: [r for r in selected if r[PATHWAY_FIELD] == p] for p in ef_pathways}
assert len(main) == 58 and len(selected) == 25
assert [len(groups[p]) for p in ef_pathways] == [15, 10]
assert all(0 <= number(r, 'LAI_target') <= 2 and 0 <= number(r, 'V_target') <= 1 for r in selected)
assert all(close(number(r, 'V_target'), number(r, 'V_current')) for r in groups[ef_pathways[0]])
assert all(close(number(r, 'V_expansion'), 0) for r in groups[ef_pathways[0]])

font_directory = Path(os.environ.get('ARIAL_FONT_DIR', 'C:/Windows/Fonts'))
for filename in ('arial.ttf', 'arialbd.ttf', 'ariali.ttf', 'arialbi.ttf'):
    if (font_directory / filename).exists():
        font_manager.fontManager.addfont(str(font_directory / filename))
try:
    font_manager.findfont('Arial', fallback_to_default=False)
except ValueError as exc:
    raise RuntimeError('Install Arial or set ARIAL_FONT_DIR to your licensed Arial font directory; fonts are not redistributed.') from exc
plt.rcParams.update({
    'font.family': 'Arial', 'font.size': 8.5, 'text.color': '#222222',
    'axes.labelsize': 9.5, 'axes.labelcolor': '#222222',
    'axes.titlesize': 10.5, 'axes.titleweight': 'bold',
    'axes.linewidth': 0.75, 'axes.edgecolor': '#444444',
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.axisbelow': True, 'axes.facecolor': 'white',
    'figure.facecolor': 'white', 'savefig.facecolor': 'white',
    'xtick.labelsize': 8.5, 'ytick.labelsize': 8.5,
    'xtick.color': '#333333', 'ytick.color': '#333333',
    'xtick.major.size': 2.5, 'ytick.major.size': 2.5,
    'xtick.major.width': 0.7, 'ytick.major.width': 0.7,
    'xtick.major.pad': 3, 'ytick.major.pad': 3,
    'grid.color': '#E6E6E6', 'grid.linewidth': 0.5,
    'legend.frameon': False, 'legend.fontsize': 8.5,
    'pdf.fonttype': 42, 'svg.fonttype': 'none', 'svg.hashsalt': STEM,
})

# Three rows and two columns: A/B, C/D, E/F. A retains its map aspect ratio.
WIDTH_MM, HEIGHT_MM = 180, 236
PAIR_WIDTH_MM = 71
LEFT_X, RIGHT_X = 16, 103
CD_BOTTOM, CD_HEIGHT = 94, 49
EF_BOTTOM, EF_HEIGHT = 31, 40
TITLE_GAP_MM = 7
fig = plt.figure(figsize=(WIDTH_MM / 25.4, HEIGHT_MM / 25.4), dpi=180)
def axes_mm(x, y, w, h):
    return fig.add_axes([x / WIDTH_MM, y / HEIGHT_MM, w / WIDTH_MM, h / HEIGHT_MM])
def text_mm(x, y, value, **kwargs):
    return fig.text(x / WIDTH_MM, y / HEIGHT_MM, value, **kwargs)
def heading(letter, ax, title, number_x):
    pos = ax.get_position()
    center = (pos.x0 + pos.x1) * WIDTH_MM / 2
    height = pos.y1 * HEIGHT_MM + TITLE_GAP_MM
    text_mm(center, height, title, ha='center', va='center', fontsize=10.5, weight='bold')
    text_mm(number_x, height, f'({letter})', ha='left', va='center', fontsize=11.5, weight='bold')
def xlabel_at(ax, value, y_mm):
    ax.set_xlabel(value)
    ax.xaxis.set_label_coords(0.5, (y_mm / HEIGHT_MM - ax.get_position().y0) / ax.get_position().height)
    ax.xaxis.label.set_verticalalignment('center')

text_mm(90, 230, 'Final management pathways across the Three-North region',
        ha='center', va='center', fontsize=12.5, weight='bold')

# A: retain all map geography, the north arrow and the scale bar. Crop only the
# external page whitespace and duplicate bottom legend. Replace the two-line
# bitmap heading and outer degree labels with matching vector Arial text.
# Pixel coordinates below were read from and visually checked against this TIFF.
with Image.open(MAP_FILE) as im:
    map_original_size = list(im.size)
    map_original_dpi = [float(v) for v in im.info.get('dpi', ())]
    map_rgb = np.array(im.convert('RGB'))
map_crop_box = (300, 240, 2390, 1447)
crop_left, crop_top, crop_right, crop_bottom = map_crop_box
original_crop = map_rgb[crop_top:crop_bottom, crop_left:crop_right].copy()
map_crop = original_crop.copy()
bitmap_text_regions = [
    (300, 240, 2390, 340),   # Original longitude numerals; ticks begin below 340.
    (300, 345, 400, 1447),   # Original latitude numerals; map/ticks start at x > 400.
    (850, 400, 1925, 544),   # First line including descenders, in empty map space.
    (1100, 525, 1710, 680),  # Second line including descenders, in empty map space.
]
for x0, y0, x1, y1 in bitmap_text_regions:
    map_crop[y0 - crop_top:y1 - crop_top, x0 - crop_left:x1 - crop_left] = 255
# Check that no pixel carrying any of the five pathway colors was changed.
for _, _, color in PATHWAYS:
    rgb = np.round(np.array(colors.to_rgb(color)) * 255).astype(np.uint8)
    assert np.array_equal((original_crop == rgb).all(axis=2), (map_crop == rgb).all(axis=2)), color
map_h_px, map_w_px = map_crop.shape[:2]
TOP_BOTTOM, TOP_HEIGHT = 164, 49
map_display_height_mm = TOP_HEIGHT
map_display_width_mm = map_display_height_mm * map_w_px / map_h_px
assert map_display_width_mm <= 85
map_display_x = 4 + (85 - map_display_width_mm) / 2
ax_a = axes_mm(map_display_x, TOP_BOTTOM, map_display_width_mm, map_display_height_mm)
ax_a.imshow(map_crop, extent=(0, map_w_px, map_h_px, 0), interpolation='none', aspect='equal')
ax_a.set_xlim(0, map_w_px)
ax_a.set_ylim(map_h_px, 0)
ax_a.set_axis_off()
heading('a', ax_a, 'Final management pathways', 4)
for longitude, x_pixel in zip(range(70, 131, 10), [604.5, 897.5, 1171.5, 1433.5, 1692.5, 1954.5, 2228.5]):
    ax_a.text(x_pixel - crop_left, 285 - crop_top, f'{longitude}°',
              ha='center', va='center', fontsize=8, color='#222222')
for latitude, y_pixel in zip([50, 40, 30], [416.5, 916.5, 1397.5]):
    ax_a.text(351 - crop_left, y_pixel - crop_top, f'{latitude}°',
              ha='center', va='center', rotation=90, fontsize=8, color='#222222')

# B: the input percentages already use the 0-100 scale.
ax_b = axes_mm(128, TOP_BOTTOM, 46, TOP_HEIGHT)
heading('b', ax_b, 'Regional area shares', 90)
b_labels = ['Sparse/open\nconservation', 'Close-to-nature\nmanagement',
            'GDE conservation\n& recovery', 'Low-tree mixed\nrestoration', 'Herbaceous recovery']
b_values = np.array([number(r, 'Area_share_pct') for r in area_rows])
ax_b.barh(np.arange(5), b_values, height=0.6,
          color=[p[2] for p in PATHWAYS], edgecolor='none', linewidth=0, zorder=2)
ax_b.set_yticks(np.arange(5), b_labels, fontsize=8.3)
ax_b.tick_params(axis='y', length=0, pad=5)
ax_b.set_ylim(4.5, -0.5)
ax_b.set_xlim(0, 50)
ax_b.set_xticks([0, 10, 20, 30, 40, 50])
ax_b.grid(axis='x')
xlabel_at(ax_b, 'Area share (%)', 155.5)
for y, value in enumerate(b_values):
    ax_b.annotate(f'{value:.1f}%', (value, y), xytext=(4, 0), textcoords='offset points',
                  va='center', fontsize=8.5, color='#222222')

# C and D: same plot dimensions and the same physical column width.
ax_c = axes_mm(LEFT_X, CD_BOTTOM, PAIR_WIDTH_MM, CD_HEIGHT)
ax_d = axes_mm(RIGHT_X, CD_BOTTOM, PAIR_WIDTH_MM, CD_HEIGHT)
heading('c', ax_c, 'Pathways across GDE levels', 4)
heading('d', ax_d, 'Pathways across aridity classes', 90)
physical_bar_width_mm = 11.2
stack_labels = []
def stacked(ax, matrix, labels, xlabel):
    count = len(labels)
    x = np.arange(count)
    bottoms = np.zeros(count)
    bar_width = physical_bar_width_mm * count / PAIR_WIDTH_MM
    for k, (_, _, color) in enumerate(PATHWAYS):
        vals = matrix[:, k]
        nonzero = vals > 0
        ax.bar(x[nonzero], vals[nonzero], bottom=bottoms[nonzero], width=bar_width,
               color=color, edgecolor='none', linewidth=0, zorder=2)
        for i, value in enumerate(vals):
            if value >= 5:
                t = ax.text(i, bottoms[i] + value / 2, f'{value:.1f}%',
                            ha='center', va='center', fontsize=8,
                            color='white' if k in (2, 3) else '#222222')
                stack_labels.append((t, ax, i, bottoms[i], value, bar_width))
        bottoms += vals
    ax.set_xlim(-0.5, count - 0.5)
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.set_xticks(x, labels, fontsize=8)
    ax.grid(axis='y')
    ax.set_ylabel('Within-group area share (%)', labelpad=5)
    xlabel_at(ax, xlabel, 83.5)

stacked(ax_c, gde_matrix, [f'GDE {g}' for g in gde_levels], 'GDE constraint level')
aridity_display = {'hyper-arid': 'Hyper-arid', 'arid': 'Arid', 'semi-arid': 'Semi-arid',
                   'dry sub-humid': 'Dry\nsub-humid', 'humid/sub-humid': 'Humid/\nsub-humid'}
stacked(ax_d, aridity_matrix, [aridity_display[a] for a in aridity_classes], 'Aridity class')

# E and F: identical, deterministic horizontal offsets for each ClassCode.
# Offset placement avoids marker collisions in BOTH panels, without altering y.
X_LIMITS = (-0.62, 1.62)
POINT_DIAMETER_PT = 3.3
MIN_POINT_SEPARATION_PT = 3.8
x_points_per_unit = PAIR_WIDTH_MM / 25.4 * 72 / (X_LIMITS[1] - X_LIMITS[0])
y_points_per_lai = EF_HEIGHT / 25.4 * 72 / 2
y_points_per_coverage = EF_HEIGHT / 25.4 * 72 / 100
candidate_offsets = [0]
for step in range(1, 6):
    candidate_offsets.extend([step * 0.045, -step * 0.045])
offsets = {}
for pathway in ef_pathways:
    placed = []
    for row in groups[pathway]:
        lai = number(row, 'LAI_target')
        occupancy = number(row, 'V_target') * 100
        for offset in candidate_offsets:
            valid = all(
                math.hypot((offset - ox) * x_points_per_unit, (lai - oy) * y_points_per_lai) >= MIN_POINT_SEPARATION_PT
                and math.hypot((offset - ox) * x_points_per_unit, (occupancy - ov) * y_points_per_coverage) >= MIN_POINT_SEPARATION_PT
                for ox, oy, ov in placed)
            if valid:
                offsets[row['ClassCode']] = offset
                placed.append((offset, lai, occupancy))
                break
        else:
            raise ValueError(f'No collision-free shared point offset for ClassCode {row["ClassCode"]}')
    shift = np.mean([offsets[r['ClassCode']] for r in groups[pathway]])
    for row in groups[pathway]:
        offsets[row['ClassCode']] -= float(shift)

ax_e = axes_mm(LEFT_X, EF_BOTTOM, PAIR_WIDTH_MM, EF_HEIGHT)
ax_f = axes_mm(RIGHT_X, EF_BOTTOM, PAIR_WIDTH_MM, EF_HEIGHT)
heading('e', ax_e, 'Target LAI by pathway', 4)
heading('f', ax_f, 'Target vegetation occupancy', 90)
box_stats = {}
for ax, field, scale, ylabel, ylim, yticks in [
    (ax_e, 'LAI_target', 1, 'Target LAI', (0, 2), [0, 0.5, 1, 1.5, 2]),
    (ax_f, 'V_target', 100, 'Target vegetation occupancy (%)', (0, 100), [0, 20, 40, 60, 80, 100]),
]:
    box_stats[field] = {}
    for j, pathway in enumerate(ef_pathways):
        rows = groups[pathway]
        vals = np.array([number(r, field) * scale for r in rows])
        color = pathway_colors[pathway]
        ax.boxplot([vals], positions=[j], widths=0.42, whis=1.5, showfliers=False, patch_artist=True,
                   manage_ticks=False,
                   boxprops={'facecolor': colors.to_rgba(color, 0.25), 'edgecolor': color, 'linewidth': 0.9},
                   medianprops={'color': '#222222', 'linewidth': 1.2},
                   whiskerprops={'color': '#444444', 'linewidth': 0.9},
                   capprops={'color': '#444444', 'linewidth': 0.9}, zorder=2)
        ax.scatter([j + offsets[r['ClassCode']] for r in rows], vals, s=POINT_DIAMETER_PT ** 2,
                   color=color, edgecolors='#333333', linewidths=0.25, zorder=3)
        stats = cbook.boxplot_stats(vals, whis=1.5)[0]
        box_stats[field][pathway] = {k: (v.tolist() if isinstance(v, np.ndarray) else float(v))
                                     for k, v in stats.items()}
        box_stats[field][pathway].update(n=len(rows), minimum=float(vals.min()), maximum=float(vals.max()))
    ax.set_xlim(*X_LIMITS)
    ax.set_ylim(*ylim)
    ax.set_yticks(yticks)
    ax.set_ylabel(ylabel, labelpad=5)
    ax.set_xticks([0, 1], [f'Close-to-nature\nmanagement\nn = {len(groups[ef_pathways[0]])}',
                           f'Low-tree mixed\nrestoration\nn = {len(groups[ef_pathways[1]])}'], fontsize=8.3)
    ax.tick_params(axis='x', length=0, pad=5)
    ax.grid(axis='y')
ax_e.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))

# Explicit two-row, left-to-right legend order: 1, 2, 3 / 4, 5.
handles = [Patch(facecolor=p[2], edgecolor='none', label=p[1]) for p in PATHWAYS]
text_mm(90, 15.6, 'Management pathways', ha='center', va='center', fontsize=8.8, weight='bold')
fig.legend(handles=handles[:3], ncol=3, loc='center', bbox_to_anchor=(0.5, 10.5 / HEIGHT_MM),
           handlelength=1.3, handleheight=0.8, handletextpad=0.5, columnspacing=1.4, borderaxespad=0)
fig.legend(handles=handles[3:], ncol=2, loc='center', bbox_to_anchor=(0.5, 5 / HEIGHT_MM),
           handlelength=1.3, handleheight=0.8, handletextpad=0.5, columnspacing=2.1, borderaxespad=0)

# Layout checks use only ticks actually inside the plotted axis ranges.
fig.canvas.draw()
renderer = fig.canvas.get_renderer()
visible_texts = list(fig.texts)
for ax in fig.axes:
    visible_texts.extend([ax.title, ax.xaxis.label, ax.yaxis.label, *ax.texts])
    if not ax.axison:
        continue
    for axis, limits in ((ax.xaxis, ax.get_xlim()), (ax.yaxis, ax.get_ylim())):
        for tick in axis.get_major_ticks():
            if min(limits) <= tick.get_loc() <= max(limits):
                visible_texts.extend([tick.label1, tick.label2])
for legend in fig.legends:
    visible_texts.extend(legend.get_texts())
visible_texts = list({id(t): t for t in visible_texts if t.get_visible() and t.get_text()}.values())
text_boxes = [(t.get_text(), t.get_window_extent(renderer)) for t in visible_texts]
outside = [text for text, b in text_boxes if b.x0 < 0 or b.y0 < 0 or b.x1 > fig.bbox.width or b.y1 > fig.bbox.height]
overlaps = [(ta, tb) for i, (ta, a) in enumerate(text_boxes) for tb, b in text_boxes[i + 1:] if a.overlaps(b)]
assert not outside, f'Text outside canvas: {outside}'
assert not overlaps, f'Overlapping texts: {overlaps}'
for label, ax, x, bottom, value, width in stack_labels:
    label_box = label.get_window_extent(renderer)
    lower = ax.transData.transform((x - width / 2, bottom))
    upper = ax.transData.transform((x + width / 2, bottom + value))
    assert label_box.x0 >= lower[0] - 0.5 and label_box.x1 <= upper[0] + 0.5, label.get_text()
    assert label_box.y0 >= lower[1] - 0.5 and label_box.y1 <= upper[1] + 0.5, label.get_text()
for a, b in [(ax_c, ax_d), (ax_e, ax_f)]:
    assert np.allclose(a.get_position().bounds[1:], b.get_position().bounds[1:])
assert [len(c.get_offsets()) for c in ax_e.collections] == [15, 10]
assert [len(c.get_offsets()) for c in ax_f.collections] == [15, 10]

metadata = {'Title': 'Final management pathways across the Three-North region',
            'Subject': 'Figure 5A-F: spatial management pathways, regional and within-group area shares, and unweighted target distributions.'}
fig.savefig(OUT / f'{STEM}.pdf', metadata=metadata)
fig.savefig(OUT / f'{STEM}.svg')
fig.savefig(OUT / f'{STEM}_600dpi.png', dpi=600)
fig.savefig(OUT / f'{STEM}_600dpi.tiff', dpi=600, pil_kwargs={'compression': 'tiff_lzw'})
tiff_path = OUT / f'{STEM}_600dpi.tiff'
with Image.open(tiff_path) as im:
    rgb = im.convert('RGB')
rgb.save(tiff_path, compression='tiff_lzw', dpi=(600, 600))

pdf = PdfReader(OUT / f'{STEM}.pdf')
assert len(pdf.pages) == 1 and len(pdf.pages[0].images) == 1
page = pdf.pages[0]
assert abs(float(page.mediabox.width) / 72 * 25.4 - WIDTH_MM) < 1e-6
assert abs(float(page.mediabox.height) / 72 * 25.4 - HEIGHT_MM) < 1e-6
embedded_fonts = []
for ref in page['/Resources']['/Font'].values():
    font = ref.get_object()
    assert 'Arial' in font['/BaseFont']
    assert '/FontFile2' in font['/DescendantFonts'][0].get_object()['/FontDescriptor']
    embedded_fonts.append(str(font['/BaseFont']))
with Image.open(OUT / f'{STEM}_600dpi.png') as im:
    png_info = {'pixels': list(im.size), 'dpi': list(im.info['dpi'])}
    assert all(abs(v - 600) < 0.1 for v in im.info['dpi'])

point_rows = []
for j, pathway in enumerate(ef_pathways):
    for r in groups[pathway]:
        point_rows.append({'ClassCode': r['ClassCode'], PATHWAY_FIELD: pathway,
                           'LAI_target': number(r, 'LAI_target'), 'V_target': number(r, 'V_target'),
                           'V_target_pct': number(r, 'V_target') * 100,
                           'shared_horizontal_offset': offsets[r['ClassCode']], 'x_position_E_and_F': j + offsets[r['ClassCode']]})
with (OUT / 'Figure5_EF_plotted_units.csv').open('w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=list(point_rows[0]))
    writer.writeheader()
    writer.writerows(point_rows)

report = {
    'sources': {key: {'path': str(SOURCE / name), 'rows': len(data[key]),
                     'sha256': hashlib.sha256((SOURCE / name).read_bytes()).hexdigest()} for key, name in FILES.items()},
    'scope': 'Complete Figure 5A-F, with the supplied map in panel A',
    'map': {'source': str(MAP_FILE), 'source_sha256': hashlib.sha256(MAP_FILE.read_bytes()).hexdigest(),
            'source_size_pixels': map_original_size, 'source_dpi': map_original_dpi,
            'crop_box_pixels': list(map_crop_box), 'cropped_size_pixels': [map_w_px, map_h_px],
            'display_size_mm': [map_display_width_mm, map_display_height_mm],
            'effective_map_dpi': map_w_px / (map_display_width_mm / 25.4),
            'bitmap_text_regions_replaced': bitmap_text_regions,
            'geography_and_pathway_pixels_preserved': True,
            'original_aspect_ratio_preserved': True,
            'legend': 'Duplicate bitmap legend omitted; five-color common legend used'},
    'n_all_units': len(main), 'n_EF_units': len(selected), 'n_without_targets': len(unselected),
    'total_area_km2': total_area, 'regional_area_share_pct': b_values.tolist(),
    'gde_levels_in_original_code_order': gde_levels, 'gde_percentage_matrix': gde_matrix.tolist(),
    'aridity_classes_in_plot_order': aridity_classes, 'aridity_percentage_matrix': aridity_matrix.tolist(),
    'boxplot_stats_unweighted': box_stats,
    'checks': {'area_summaries_reconcile_to_58_unit_main_table': True, 'all_group_percentages_sum_to_100': True,
               'zero_combinations_retained': True, 'source_percentages_not_rescaled': True,
               'only_V_target_multiplied_by_100': True, 'same_25_ClassCodes_in_E_and_F': True,
               'same_horizontal_offsets_in_E_and_F': True, 'all_25_points_shown_once_per_panel': True,
               'near_natural_targets_equal_current_coverage': True, 'no_area_weighting': True,
               'CD_plot_sizes_equal': True, 'CD_bar_widths_equal': True, 'EF_plot_sizes_equal': True,
               'no_visible_text_overlap_or_clipping': True},
    'figure_size_mm': [WIDTH_MM, HEIGHT_MM], 'png': png_info,
    'embedded_pdf_fonts': embedded_fonts, 'PDF_raster_image_count': len(page.images),
}
(OUT / 'Figure5_data_checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
caption = f'''Figure 5. Final management pathways across the Three-North region.

(a) Spatial distribution of the five final management pathways, using the supplied management map. The geographic proportions, boundary, north arrow and scale bar are retained. Pathway colors match panels (b–f) and the common legend.

(b) Regional area shares of the five management pathways, using the total area of all {len(main)} analytical units ({total_area:,.2f} km²) as the denominator. Bar lengths retain the original numerical precision; labels are rounded to one decimal place and may sum to 100.1%.

(c) Area composition of management pathways within each GDE level, using the area of that level as its denominator. GDE 0–3 are shown in the original code order; the numerical codes are not assumed to rank ecological constraint intensity. (d) Area composition within each aridity class, ordered from hyper-arid to humid/sub-humid. Both panels retain the supplied area percentages, including very small nonzero shares; labels are shown only for shares of at least 5%. Zero-area combinations contribute no height. Colors identify management categories rather than numerical magnitude.

(e) Target leaf area index (LAI) and (f) target vegetation occupancy (V_target × 100) for the same {len(selected)} analytical units with numerical targets: close-to-nature management, n = {len(groups[ef_pathways[0]])}; low-tree mixed restoration, n = {len(groups[ef_pathways[1]])}. Boxes show the unweighted 25th–75th percentiles across analytical units, center lines show medians, and whiskers reach the most extreme observed values within 1.5 interquartile ranges of the box edges. All unit-level observations are overlaid, including observations beyond the whiskers. Points have identical small horizontal offsets in (e) and (f), while their vertical positions retain the actual observed target values. The per-unit LAI_target_p05/p95 and V_target_p05/p95 fields are not used for these boxes.

Panels (b–d) cover all {len(main)} analytical units; panels (e–f) use unweighted data for the {len(selected)} units with numerical targets. The other {len(unselected)} units were not assigned numerical targets and are excluded from panels (e–f). In the {len(groups[ef_pathways[0]])} close-to-nature management units, V_target retains existing vegetation occupancy, so these target values do not represent additional restoration area. Panel (f) shows total target vegetation occupancy, not V_expansion or within-vegetation life-form proportions.
'''
(OUT / 'Figure5_caption_EN.txt').write_text(caption, encoding='utf-8')
script_copy = OUT / 'Figure5_plot.py'
if Path(__file__).resolve() != script_copy.resolve():
    shutil.copy2(__file__, script_copy)
print(json.dumps({'n_all_units': len(main), 'n_EF_units': len(selected), 'total_area_km2': total_area,
                  'area_share_labels': [f'{v:.1f}%' for v in b_values],
                  'group_n': {pathway_labels[p]: len(groups[p]) for p in ef_pathways},
                  'figure_size_mm': [WIDTH_MM, HEIGHT_MM], 'png': png_info,
                  'outputs': [str(p) for p in OUT.iterdir()]}, ensure_ascii=False, indent=2))
