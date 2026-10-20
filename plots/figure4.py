"""Reproducible Figure 4; source CSVs are read only. Run from an environment installed with requirements.txt."""
from pathlib import Path
import os
import sys
import csv
import json
import math
import hashlib
import shutil
from collections import Counter, defaultdict

WORKSPACE = Path(__file__).resolve().parents[1]
os.environ['MPLCONFIGDIR'] = str(WORKSPACE / 'build' / 'matplotlib_cache')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager, colors
from matplotlib.lines import Line2D
from matplotlib.legend_handler import HandlerLine2D
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
from PIL import Image
from pypdf import PdfReader

SOURCE = WORKSPACE / 'data' / 'figure4'
OUT = WORKSPACE / 'build' / 'figure4'
OUT.mkdir(parents=True, exist_ok=True)
STEM = 'Figure4_Pareto_water_safe'
FILENAMES = {
    'front': 'R07_ParetoFront_REVISED.csv',
    'best': 'R07_BestCompromise_REVISED.csv',
    'ranges': 'R07_ParetoRanges_ByClass_REVISED.csv',
    'summary': 'R07_BestSummary_REVISED.csv',
}
data = {}
for key, name in FILENAMES.items():
    with (SOURCE / name).open(encoding='utf-8-sig', newline='') as f:
        data[key] = list(csv.DictReader(f))
front, best, ranges, summary = (data[k] for k in ('front', 'best', 'ranges', 'summary'))
OBJECTIVES = ['obj1_sand_benefit', 'obj2_eco_stability', 'obj3_water_pressure', 'obj4_gde_risk']
COMPONENTS = [('tree', 'Tree', '#009E73'), ('shrub', 'Shrub', '#E69F00'), ('herb', 'Herbaceous', '#0072B2')]
required = {
    'front': ['ClassCode', 'CandidateID', 'LAI_target', *OBJECTIVES, 'q_tree', 'q_shrub', 'q_herb'],
    'best': ['ClassCode', 'CandidateID', 'LAI_target', 'LifeFormStructure', *OBJECTIVES, 'q_tree', 'q_shrub', 'q_herb'],
    'ranges': ['ClassCode', *[f'q_{c}_{edge}' for c, _, _ in COMPONENTS for edge in ('min', 'max')]],
    'summary': ['LifeFormStructure', 'n_ClassCode'],
}
for key, fields in required.items():
    assert data[key], f'Empty file: {key}'
    assert set(fields) <= data[key][0].keys(), f'Missing columns: {key}'

def class_id(row):
    v = float(row['ClassCode'])
    assert v.is_integer()
    return int(v)

def values(rows, key):
    arr = np.array([float(row[key]) for row in rows])
    assert np.isfinite(arr).all(), f'Nonfinite values: {key}'
    return arr

by_class = defaultdict(list)
for row in front:
    by_class[class_id(row)].append(row)
best_by_class = {class_id(row): row for row in best}
ranges_by_class = {class_id(row): row for row in ranges}
assert len(best_by_class) == len(best), 'Duplicate selected ClassCode'
assert len(ranges_by_class) == len(ranges), 'Duplicate range ClassCode'
assert set(by_class) == set(best_by_class) == set(ranges_by_class), 'Mismatched ClassCode sets'
ids = sorted(best_by_class)
front_by_candidate = {(class_id(row), row['CandidateID']): row for row in front}
assert len(front_by_candidate) == len(front), 'Duplicate candidate keys'
for rows in (front, best):
    for field in [*OBJECTIVES, 'LAI_target', 'q_tree', 'q_shrub', 'q_herb']:
        values(rows, field)
    q = sum(values(rows, f'q_{c}') for c, _, _ in COMPONENTS)
    assert np.allclose(q, 1, rtol=0, atol=1e-12), 'q components do not sum to 1'
for cid in ids:
    selected = best_by_class[cid]
    original = front_by_candidate[(cid, selected['CandidateID'])]
    for field in [*OBJECTIVES, 'LAI_target', 'q_tree', 'q_shrub', 'q_herb']:
        assert math.isclose(float(selected[field]), float(original[field]), rel_tol=0, abs_tol=1e-12), (cid, field)
    r = ranges_by_class[cid]
    if 'n_pareto' in r:
        assert int(r['n_pareto']) == len(by_class[cid])
    for c, _, _ in COMPONENTS:
        actual = values(by_class[cid], f'q_{c}')
        lo, hi = float(r[f'q_{c}_min']), float(r[f'q_{c}_max'])
        assert math.isclose(lo, float(actual.min()), abs_tol=1e-12)
        assert math.isclose(hi, float(actual.max()), abs_tol=1e-12)
        assert 0 <= lo <= hi <= 1
        assert lo - 1e-12 <= float(selected[f'q_{c}']) <= hi + 1e-12
counts = Counter(row['LifeFormStructure'] for row in best)
summary_counts = Counter()
for row in summary:
    summary_counts[row['LifeFormStructure']] += int(row['n_ClassCode'])
assert counts == summary_counts, 'Summary and selected structure counts differ'

font_directory = Path(os.environ.get('ARIAL_FONT_DIR', 'C:/Windows/Fonts'))
for filename in ('arial.ttf', 'arialbd.ttf', 'ariali.ttf', 'arialbi.ttf'):
    if (font_directory / filename).exists():
        font_manager.fontManager.addfont(str(font_directory / filename))
try:
    font_manager.findfont('Arial', fallback_to_default=False)
except ValueError as exc:
    raise RuntimeError('Install Arial or set ARIAL_FONT_DIR to your licensed Arial font directory; fonts are not redistributed.') from exc
plt.rcParams.update({
    'font.family': 'Arial', 'font.size': 8.5,
    'text.color': '#222222', 'axes.labelcolor': '#222222',
    'axes.labelsize': 10, 'axes.titlesize': 11, 'axes.titleweight': 'bold',
    'axes.edgecolor': '#444444', 'axes.linewidth': 0.75,
    'axes.spines.top': False, 'axes.spines.right': False,
    'xtick.color': '#333333', 'ytick.color': '#333333',
    'xtick.labelsize': 8.5, 'ytick.labelsize': 8.5,
    'xtick.major.width': 0.7, 'ytick.major.width': 0.7,
    'xtick.major.size': 2.5, 'ytick.major.size': 2.5,
    'xtick.major.pad': 3, 'ytick.major.pad': 3,
    'grid.color': '#E6E6E6', 'grid.linewidth': 0.45,
    'axes.axisbelow': True, 'legend.fontsize': 8.5, 'legend.frameon': False,
    'figure.facecolor': 'white', 'axes.facecolor': 'white', 'savefig.facecolor': 'white',
    'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
    'svg.hashsalt': STEM,
})

WIDTH_MM, HEIGHT_MM = 180, 207
fig = plt.figure(figsize=(WIDTH_MM / 25.4, HEIGHT_MM / 25.4), dpi=150)
def axes_mm(x, y, w, h, **kwargs):
    return fig.add_axes([x / WIDTH_MM, y / HEIGHT_MM, w / WIDTH_MM, h / HEIGHT_MM], **kwargs)
def text_mm(x, y, text, **kwargs):
    return fig.text(x / WIDTH_MM, y / HEIGHT_MM, text, **kwargs)
PLOT_WIDTH_MM = 65
TITLE_OFFSET_MM = 12
TOP_Y, TOP_HEIGHT = 134, 54
LOWER_Y, LOWER_HEIGHT = 22, 78
LEFT_X, RIGHT_X = 16, 100
panel_titles = []
def panel_header(letter, label_x, plot_x, plot_width, plot_top, title):
    """Center the title on its plot area, independently of the panel letter."""
    y = plot_top + TITLE_OFFSET_MM
    text_mm(label_x, y, f'({letter})', fontsize=11, weight='bold', va='center')
    label = text_mm(plot_x + plot_width / 2, y, title, fontsize=11,
                    weight='bold', ha='center', va='center')
    panel_titles.append(label)
def padded_limits(a, b):
    lo, hi = min(a.min(), b.min()), max(a.max(), b.max())
    pad = (hi - lo) * 0.05
    return float(lo - pad), float(hi + pad)

ax_a = axes_mm(LEFT_X, TOP_Y, PLOT_WIDTH_MM, TOP_HEIGHT)
ax_b = axes_mm(RIGHT_X, TOP_Y, PLOT_WIDTH_MM, TOP_HEIGHT)
panel_header('a', 4, LEFT_X, PLOT_WIDTH_MM, TOP_Y + TOP_HEIGHT, 'Benefit–water trade-off')
panel_header('b', 88, RIGHT_X, PLOT_WIDTH_MM, TOP_Y + TOP_HEIGHT, 'Stability–GDE risk trade-off')
lai = values(front, 'LAI_target')
norm = colors.Normalize(vmin=float(lai.min()), vmax=float(lai.max()))
# One continuous reversed viridis scale for BOTH projections and their colorbar.
# Only soften the low-value yellow end; preserve the teal and dark-purple end.
color_positions = np.linspace(0, 1, 1024)
color_table = plt.colormaps['viridis_r'](color_positions)
soften = 0.8 * np.clip(1 - color_positions / 0.38, 0, 1) ** 2
ivory = np.array(colors.to_rgb('#EFE8CC'))
color_table[:, :3] = (color_table[:, :3] * (1 - soften[:, None])
                       + ivory * soften[:, None])
lai_cmap = colors.LinearSegmentedColormap.from_list('viridis_r_soft_yellow', color_table, N=1024)
plot_pairs = [
    (ax_a, 'obj1_sand_benefit', 'obj3_water_pressure', 'Sand-fixation benefit score', 'Water-pressure score'),
    (ax_b, 'obj2_eco_stability', 'obj4_gde_risk', 'Ecological-stability score', 'GDE-risk score'),
]
scatter_collections = []
for ax, x_key, y_key, x_label, y_label in plot_pairs:
    x, y = values(front, x_key), values(front, y_key)
    bx, by = values(best, x_key), values(best, y_key)
    ax.grid(True)
    points = ax.scatter(x, y, c=lai, cmap=lai_cmap, norm=norm, marker='o', s=18,
                        alpha=0.65, edgecolors='none', linewidths=0, zorder=2)
    scatter_collections.append(points)
    ax.scatter(bx, by, marker='D', s=55, facecolors='none', edgecolors='black',
               linewidths=0.9, zorder=3)
    ax.set(xlim=padded_limits(x, bx), ylim=padded_limits(y, by), xlabel=x_label, ylabel=y_label)
    ax.xaxis.set_major_locator(MultipleLocator(0.1))
    ax.yaxis.set_major_locator(MultipleLocator(0.2 if ax is ax_a else 0.1))
    ax.xaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    ax.xaxis.labelpad = 5
    ax.yaxis.labelpad = 5

cax = axes_mm(170, TOP_Y, 2.3, TOP_HEIGHT)
cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=lai_cmap), cax=cax)
cb.ax.set_title('Target LAI', fontsize=8.5, weight='normal', pad=7)
cb.ax.tick_params(labelsize=8, length=2, pad=2)
cb.set_ticks(np.arange(0.5, 3.01, 0.5))
cb.ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
cb.outline.set_linewidth(0.6)
cb.outline.set_edgecolor('#444444')
cb.solids.set_rasterized(False)
cb.solids.set_edgecolor('face')  # Avoid thin renderer seams in the vector colorbar.

scatter_handles = [
    Line2D([], [], linestyle='none', marker='o', markersize=math.sqrt(18),
           markerfacecolor=lai_cmap(0.5), markeredgewidth=0, alpha=0.65,
           label='Pareto solutions'),
    Line2D([], [], linestyle='none', marker='D', markersize=math.sqrt(55),
           markerfacecolor='none', markeredgecolor='black', markeredgewidth=0.9,
           label='Selected compromise'),
]
fig.legend(handles=scatter_handles, loc='center', bbox_to_anchor=(92 / WIDTH_MM, 119.5 / HEIGHT_MM),
           ncol=2, handletextpad=0.55, columnspacing=2.6, borderaxespad=0)

panel_header('c', 4, LEFT_X, PLOT_WIDTH_MM, LOWER_Y + LOWER_HEIGHT, 'Selected vegetation structures')
ax_c = axes_mm(LEFT_X, LOWER_Y, PLOT_WIDTH_MM, LOWER_HEIGHT)
structure_order = ['low-tree mixed', 'shrub-herbaceous']
structure_order = [s for s in structure_order if s in counts] + sorted(set(counts) - set(structure_order))
structure_labels = {'low-tree mixed': 'Low-tree mixed', 'shrub-herbaceous': 'Shrub–herbaceous'}
structure_colors = {'low-tree mixed': '#009E73', 'shrub-herbaceous': '#E69F00'}
n = len(best)
bar_values = [counts[s] for s in structure_order]
bar_y = np.arange(len(structure_order))
bar_height = 0.42
ax_c.barh(bar_y, bar_values, height=bar_height, color=[structure_colors.get(s, '#0072B2') for s in structure_order],
          edgecolor='none', linewidth=0, zorder=2)
ax_c.set_yticks([])
ax_c.set_ylim(len(structure_order) - 0.4, -0.6)
count_limit = math.ceil(max(bar_values) * 1.36 / 5) * 5
ax_c.set_xlim(0, count_limit)
ax_c.set_xticks(np.arange(0, count_limit + 1, 5))
ax_c.set_xlabel('Number of analytical units', labelpad=5)
ax_c.xaxis.set_label_coords(0.5, (11.2 - LOWER_Y) / LOWER_HEIGHT)
ax_c.xaxis.label.set_verticalalignment('center')
ax_c.grid(axis='x')
for y, structure in zip(bar_y, structure_order):
    ax_c.text(0.018, y - bar_height / 2 - 0.09, structure_labels.get(structure, structure),
              transform=ax_c.get_yaxis_transform(), fontsize=9, ha='left', va='bottom')
for y, val in zip(bar_y, bar_values):
    pct = val / n * 100
    pct_text = f'{pct:.0f}' if math.isclose(pct, round(pct), abs_tol=1e-9) else f'{pct:.1f}'
    ax_c.annotate(f'{val} ({pct_text}%)', (val, y), xytext=(4, 0), textcoords='offset points',
                  va='center', fontsize=9.5, weight='bold', annotation_clip=False)
text_mm(LEFT_X + PLOT_WIDTH_MM / 2, LOWER_Y + LOWER_HEIGHT + 4.5,
        f'n = {n} analytical units', fontsize=8.5, ha='center', va='center')

panel_header('d', 88, RIGHT_X, PLOT_WIDTH_MM, LOWER_Y + LOWER_HEIGHT, 'Pareto ranges of life-form proportions')
range_axes = []
ypos = np.arange(len(ids))
COLUMN_GAP_MM = 3.5
COLUMN_WIDTH_MM = (PLOT_WIDTH_MM - 2 * COLUMN_GAP_MM) / 3
for j, (c, name, color) in enumerate(COMPONENTS):
    ax = axes_mm(RIGHT_X + (COLUMN_WIDTH_MM + COLUMN_GAP_MM) * j,
                 LOWER_Y, COLUMN_WIDTH_MM, LOWER_HEIGHT,
                 sharey=range_axes[0] if range_axes else None)
    range_axes.append(ax)
    ax.set_title(name, fontsize=9, pad=8)
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.5, 1], ['0', '0.5', '1.0'])
    ax.set_ylim(len(ids) - 0.4, -0.6)
    ax.set_yticks(ypos)
    if j == 0:
        ax.set_yticklabels([str(cid) for cid in ids], fontsize=8)
        ax.set_ylabel('ClassCode', fontsize=10, labelpad=5)
    else:
        ax.tick_params(axis='y', labelleft=False)
    ax.tick_params(axis='y', length=0)
    ax.grid(axis='y', linewidth=0.4, color='#EEEEEE')
    for y, cid in enumerate(ids):
        r = ranges_by_class[cid]
        lo, hi = float(r[f'q_{c}_min']), float(r[f'q_{c}_max'])
        selected = float(best_by_class[cid][f'q_{c}'])
        if not math.isclose(lo, hi, abs_tol=1e-12):
            ax.hlines(y, lo, hi, color=color, linewidth=1.1, zorder=2)
            ax.plot([lo, hi], [y, y], linestyle='none', marker='|', markersize=3.6,
                    markeredgewidth=1.1, color=color, clip_on=False, zorder=2)
        ax.plot(selected, y, marker='o', linestyle='none', markersize=3,
                markerfacecolor=color, markeredgecolor='black', markeredgewidth=0.35,
                zorder=3, clip_on=False)
text_mm(RIGHT_X + PLOT_WIDTH_MM / 2, 11.2, 'Proportion within vegetated area',
        ha='center', va='center', fontsize=10)
range_handles = [
    Line2D([], [], color='#666666', linewidth=1.1, marker='|', markersize=3.6,
           markeredgewidth=1.1, label='Pareto min–max'),
    Line2D([], [], linestyle='none', marker='o', markersize=3, markerfacecolor='#888888',
           markeredgecolor='black', markeredgewidth=0.35, label='Selected compromise'),
]
fig.legend(handles=range_handles, loc='center', bbox_to_anchor=((RIGHT_X + PLOT_WIDTH_MM / 2) / WIDTH_MM, 4.7 / HEIGHT_MM),
           ncol=2, handlelength=1.5, handletextpad=0.5, columnspacing=1.3, borderaxespad=0,
           handler_map={range_handles[0]: HandlerLine2D(numpoints=2)})

# Check the actual visible texts, excluding locator ticks outside the axis limits.
# No tight cropping: the physical 180 mm figure width must be retained.
fig.canvas.draw()
renderer = fig.canvas.get_renderer()
visible_texts = list(fig.texts)
for ax in fig.axes:
    visible_texts.extend([ax.title, ax.xaxis.label, ax.yaxis.label, *ax.texts])
    for axis, limits in ((ax.xaxis, ax.get_xlim()), (ax.yaxis, ax.get_ylim())):
        for tick in axis.get_major_ticks():
            if min(limits) <= tick.get_loc() <= max(limits):
                visible_texts.extend([tick.label1, tick.label2])
for legend in fig.legends:
    visible_texts.extend(legend.get_texts())
visible_texts = list({id(t): t for t in visible_texts if t.get_visible() and t.get_text()}.values())
outside = []
text_boxes = []
for artist in visible_texts:
    box = artist.get_window_extent(renderer)
    text_boxes.append((artist.get_text(), box))
    if box.x0 < -0.5 or box.y0 < -0.5 or box.x1 > fig.bbox.width + 0.5 or box.y1 > fig.bbox.height + 0.5:
        outside.append(artist.get_text())
assert not outside, f'Text outside canvas: {outside}'
overlaps = [(a, b) for i, (a, box_a) in enumerate(text_boxes)
            for b, box_b in text_boxes[i + 1:] if box_a.overlaps(box_b)]
assert not overlaps, f'Overlapping texts: {overlaps}'
assert all(p.norm is norm and p.get_cmap() is lai_cmap for p in scatter_collections)
assert all(len(p.get_offsets()) == len(front) for p in scatter_collections)
assert all(len(ax.collections[1].get_offsets()) == len(best) for ax in (ax_a, ax_b))
assert cb.mappable.norm is norm and cb.mappable.get_cmap() is lai_cmap
assert np.allclose(ax_c.get_position().bounds[1::2], range_axes[0].get_position().bounds[1::2])
assert math.isclose(ax_c.get_position().width,
                    range_axes[-1].get_position().x1 - range_axes[0].get_position().x0)

metadata = {'Title': 'Figure 4. Pareto optimization of water-safe vegetation structures.',
            'Subject': 'Two-dimensional projections of per-unit four-objective Pareto sets and selected vegetation structures.'}
fig.savefig(OUT / f'{STEM}.pdf', metadata=metadata)
fig.savefig(OUT / f'{STEM}.svg')
fig.savefig(OUT / f'{STEM}.png', dpi=600)
fig.savefig(OUT / f'{STEM}_600dpi.tiff', dpi=600, pil_kwargs={'compression': 'tiff_lzw'})
# Make the journal raster RGB (white opaque background) and retain exact dpi tags.
tiff_path = OUT / f'{STEM}_600dpi.tiff'
with Image.open(tiff_path) as im:
    rgb = im.convert('RGB')
rgb.save(tiff_path, compression='tiff_lzw', dpi=(600, 600))

page = PdfReader(OUT / f'{STEM}.pdf').pages[0]
pdf_w_mm = float(page.mediabox.width) / 72 * 25.4
pdf_h_mm = float(page.mediabox.height) / 72 * 25.4
assert abs(pdf_w_mm - WIDTH_MM) < 1e-6 and abs(pdf_h_mm - HEIGHT_MM) < 1e-6
xobjects = page['/Resources'].get('/XObject', {})
assert not any(obj.get_object().get('/Subtype') == '/Image' for obj in xobjects.values()), 'Raster image in vector PDF'
with Image.open(tiff_path) as im:
    tiff_info = {'pixels': list(im.size), 'dpi': [float(v) for v in im.info['dpi']], 'mode': im.mode, 'compression': im.info['compression']}
    assert im.info['dpi'] == (600, 600) and im.mode == 'RGB'
with Image.open(OUT / f'{STEM}.png') as im:
    png_info = {'pixels': list(im.size), 'dpi': [float(v) for v in im.info['dpi']]}
    assert all(abs(v - 600) < 0.1 for v in im.info['dpi'])
font_resources = page['/Resources']['/Font']
embedded_fonts = []
for font_ref in font_resources.values():
    font = font_ref.get_object()
    descriptor = font['/DescendantFonts'][0].get_object()['/FontDescriptor']
    assert 'Arial' in font['/BaseFont'] and '/FontFile2' in descriptor
    embedded_fonts.append(str(font['/BaseFont']))

report = {
    'source_files': {key: {'path': str(SOURCE / name), 'sha256': hashlib.sha256((SOURCE / name).read_bytes()).hexdigest(),
                           'rows': len(data[key])} for key, name in FILENAMES.items()},
    'n_pareto_records': len(front), 'n_selected_units': n, 'n_range_rows': len(ranges),
    'classcodes_ascending': ids, 'structure_counts': dict(counts),
    'structure_unit_percentages': {s: counts[s] / n * 100 for s in counts},
    'lai_color_limits': [norm.vmin, norm.vmax],
    'lai_colormap': {'name': lai_cmap.name, 'direction': 'low ivory-yellow to teal to high dark blue-purple',
                    'low_hex': colors.to_hex(lai_cmap(0.0)), 'middle_hex': colors.to_hex(lai_cmap(0.5)),
                    'high_hex': colors.to_hex(lai_cmap(1.0)), 'shared_by_a_b_colorbar': True},
    'layout': {'lower_panel_plot_width_mm': PLOT_WIDTH_MM, 'lower_plot_height_mm': LOWER_HEIGHT,
               'lower_plot_bottom_mm': LOWER_Y, 'title_font_pt': 11, 'axis_label_font_pt': 10,
               'titles_centered_on_plot_area': True, 'panel_letters_separate': True},
    'objective_ranges': {k: [float(values(front, k).min()), float(values(front, k).max())] for k in OBJECTIVES},
    'projection_distinct_coordinate_counts': {
        'a': len({(r['obj1_sand_benefit'], r['obj3_water_pressure']) for r in front}),
        'b': len({(r['obj2_eco_stability'], r['obj4_gde_risk']) for r in front}),
    },
    'checks': {'unique_selected_classcodes': True, 'classcode_sets_match': True,
               'selected_candidate_values_match_pareto': True, 'range_endpoints_match_exported_pareto': True,
               'range_record_counts_match': True, 'selected_q_inside_ranges': True,
               'q_components_sum_to_one': True, 'summary_counts_match_unique_selected_units': True,
               'no_missing_or_nonfinite_plot_values': True, 'text_inside_canvas': True,
               'visible_texts_do_not_overlap': True, 'lower_plots_equal_width_and_height': True},
    'figure_size_mm': [pdf_w_mm, pdf_h_mm], 'tiff': tiff_info, 'png': png_info,
    'embedded_pdf_fonts': embedded_fonts,
    'font': 'Arial', 'points_retained_without_jitter': True,
    'interpretation': 'Ranges are minima/maxima among exported Pareto solutions; not confidence intervals or continuous feasibility. Structure shares use analytical-unit counts, not area.',
}
(OUT / 'Figure4_data_checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
caption = f'''Figure 4. Pareto optimization of water-safe vegetation structures.

(a) Sand-fixation benefit versus water-pressure scores and (b) ecological-stability versus GDE-risk scores. Colored circles show all {len(front)} exported Pareto records from {n} optimized analytical units, with a shared continuous reversed viridis scale for target leaf area index (LAI), softened to a pale ivory-yellow at low values and transitioning through teal to dark blue-purple at high values. Black open diamonds identify the {n} selected compromises supplied in the revised selection file. These are two-dimensional projections of the per-unit four-objective Pareto sets; overlapping records retain their original coordinates, and compromises were not reselected from either projection.

(c) Numbers of analytical units assigned to the selected vegetation structures: low-tree mixed, {counts.get('low-tree mixed', 0)} ({counts.get('low-tree mixed', 0)/n:.0%}); shrub–herbaceous, {counts.get('shrub-herbaceous', 0)} ({counts.get('shrub-herbaceous', 0)/n:.0%}). Percentages refer to the {n} optimized analytical units, not to proportions of the study-area surface.

(d) Pareto min–max ranges of tree, shrub, and herbaceous proportions, ordered by ascending ClassCode. Colored horizontal segments with end caps show the minima and maxima among the exported Pareto solutions; filled circles with thin black borders indicate the supplied selected compromises. A fixed range is shown as a single point. Segments are not 95% confidence intervals and do not imply that every intermediate value corresponds to a feasible solution. The proportions are conditional on vegetated area, with q_tree + q_shrub + q_herb = 1. Thus, q_tree = 0.2 denotes 20% of vegetated area; its whole-surface fraction is V_target × q_tree. Only the {n} optimized units are included; the 33 direct-management units are excluded.
'''
(OUT / 'Figure4_caption_EN.txt').write_text(caption, encoding='utf-8')
script_copy = OUT / 'Figure4_plot.py'
if Path(__file__).resolve() != script_copy.resolve():
    shutil.copy2(__file__, script_copy)
print(json.dumps({'counts': dict(counts), 'rows': {k: len(v) for k,v in data.items()}, 'lai': [norm.vmin,norm.vmax],
                  'dimensions_mm': [pdf_w_mm,pdf_h_mm], 'tiff': tiff_info,
                  'outputs': [str(p) for p in OUT.iterdir()]}, ensure_ascii=False, indent=2))
