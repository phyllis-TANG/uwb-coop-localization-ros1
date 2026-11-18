#!/usr/bin/env python3
"""Create a four-page review PDF from verified analysis outputs."""
from pathlib import Path
import csv,json
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output';OUT.mkdir(exist_ok=True)
S=json.loads((ROOT/'results/SUMMARY.json').read_text())
V=json.loads((ROOT/'results/VERIFICATION.json').read_text())
assert V['status']=='PASS'
pdfmetrics.registerFont(TTFont('ReportCN',str(ROOT/'assets/ReportSCSubset-Regular.ttf')))
INK=colors.HexColor('#18334d');BLUE=colors.HexColor('#2166AC')
styles={
 'title':ParagraphStyle('TitleCN',fontName='ReportCN',fontSize=20,leading=28,textColor=INK,spaceAfter=12),
 'sub':ParagraphStyle('SubCN',fontName='ReportCN',fontSize=10,leading=15,textColor=colors.HexColor('#596773'),spaceAfter=10),
 'h':ParagraphStyle('HeadingCN',fontName='ReportCN',fontSize=13,leading=20,textColor=BLUE,spaceBefore=8,spaceAfter=7),
 'p':ParagraphStyle('BodyCN',fontName='ReportCN',fontSize=10.5,leading=17,spaceAfter=8,wordWrap='CJK'),
 'small':ParagraphStyle('SmallCN',fontName='ReportCN',fontSize=9,leading=14,spaceAfter=7,wordWrap='CJK'),
 'cell':ParagraphStyle('CellCN',fontName='ReportCN',fontSize=9,leading=14,wordWrap='CJK'),
 'en':ParagraphStyle('English',fontName='Times-Roman',fontSize=10,leading=14,spaceAfter=9),
}
story=[]
def p(text,style='p'):return Paragraph(escape(text),styles[style])
def add(text,style='p'):story.append(p(text,style))
def table(data,widths):
    t=Table([[p(str(c),'cell') for c in row] for row in data],colWidths=widths,hAlign='LEFT',repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf3f8')),
      ('LINEABOVE',(0,0),(-1,0),.7,INK),('LINEBELOW',(0,0),(-1,0),.5,INK),
      ('LINEBELOW',(0,-1),(-1,-1),.5,INK),('VALIGN',(0,0),(-1,-1),'TOP'),
      ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
      ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    story.append(t);story.append(Spacer(1,9))
def figure(name,width):
    im=Image(str(ROOT/'figures'/name));im.drawHeight*=width/im.drawWidth;im.drawWidth=width
    story.append(im);story.append(Spacer(1,8))
def header(c,doc):
    c.saveState();w,h=A4;c.setStrokeColor(BLUE);c.setLineWidth(.6);c.line(42,h-32,w-42,h-32)
    c.setFillColor(INK);c.setFont('Helvetica',8);c.drawString(42,h-24,'UWB Cooperative Localization | Evidence Review | 2026-11-04')
    c.setFillColor(colors.grey);c.drawString(42,24,'Cross-recording analysis / archived results retain their estimator identity')
    c.drawRightString(w-42,24,str(doc.page));c.restoreState()

add('逐车协同收益：实验补强结果','title')
add('历史数据资格核实、记录影响分析、误差分解与候选图 | 2026年11月4日','sub')
add('目前最有力的新增证据','h')
add('现有十次静态确认记录的相反摆位交互，在逐条剔除后均保持方向。正常静态窗口中的误差以平均位置偏移为主。三次历史双车记录已从完整保存轨迹重算共同停靠窗口MSE，其中前两次再次出现绝对误差改善、协同排序反转的现象。')
add('逐条剔除结果：正常窗口','h')
t=[['机器人 / 方法','全部记录 T (m²)','剔除一条后的范围 (m²)']]
for r in S['E3_normal_T']:
 t.append([r['car'].replace('car','Robot ')+(' / Cooperative' if r['arm']=='J' else ' / Reduced'),
           f"{r['T_m2']:+.5f}",f"[{r['LOO_min_m2']:+.5f}, {r['LOO_max_m2']:+.5f}]"])
table(t,[150,110,247])
add('共80个逐条剔除计算涵盖正常、人员操作和恢复阶段，方向均保留。三个阶段来自相同原始记录，不能计为额外独立采集。上述范围是敏感性范围，不是置信区间。','small')
add('历史数据的实际可用范围','h')
table([['数据','本轮完成 / 可继续推进'],
 ['E2 三次历史双车','已核对并重算36组共同停点MSE、12组校准变化；保留批处理估计器身份。'],
 ['10月18日其他记录','四条静态XY候选、四条运动候选、四条标量测距记录，逐条列明参考和后续动作。'],
 ['10月24-25日','八条正式候选、十四条试录/方向记录；保留原留出身份，按参考及配置核实。'],
 ['E3 / E4','E3十条确认记录均有匹配轨迹；E4五段、32条停点对照已齐，计算C仍需校正条件。']], [125,382])
add('完整116行台账已保留原始字段并补充分析资格。时长、窗口、位置与采集批次分别登记；尚未证实的总采集小时数没有写入结果。','small')

story.append(PageBreak())
add('按采集时间展示跨记录变化','title')
figure('E3_calibration_change_chronology.png',330)
add('图1. 十次静态确认记录的正常窗口。红圆表示Cooperative，橙三角表示Reduced；每个点对应一条原始记录，横轴保留实际采集时间间隔。灰底区是摆位B。','small')
add('方向与幅度如何解读','h')
add('D为协同MSE减独立MSE，负值表示协同有益；C为校正后D减原始D，正值表示校准后协同相对优势下降。T为B组平均C减A组平均C，是组间对比。')
add('摆位A的两个机器人分别呈现一致的C方向。摆位B中Robot 1的六条C均为正；Robot 2的C接近零，四条为正、两条为负。图中保留全部结果，没有按符号筛选。')
add('正常窗口合计150秒；全部三个阶段合计375秒。保存轨迹跨度之和为2498秒（41分38秒）；首尾保存时刻相隔约3848秒（64分08秒）。这些量均不能替代整个历史数据集的原始包时长。','small')
add('当前A先采、B后采，时间与摆位相伴变化。因此该图支持跨记录描述，尚不能单独识别时间漂移或跨会话稳定性。建议暂用“Cross-Recording Variability and Calibration Transfer”作为分析主题。','small')

story.append(PageBreak())
add('误差机制：平均偏移与窗口内波动','title')
figure('E3_mean_offset_and_spread.png',507)
add('图2. 逐记录分解后取等权均值。蓝方块为平均误差向量的模平方，橙圆为围绕均值的位置波动；对数纵轴使较小的波动项清晰可见。I/C/R分别为Independent、Cooperative、Reduced。','small')
add('MSE = squared mean error + within-window centered spread','en')
add('在全部120组正常窗口的“记录×校准条件×机器人×方法”组合中，平均偏移平方占各自MSE的比例均超过99.01%。这解释了轨迹可能很紧凑，但相对参考位置仍有明显误差。这里的偏移是相对测量参考的有限窗口量，并非对总体统计偏差的独立估计。')
table([['Cooperative','T：偏移项 (m²)','T：波动项 (m²)'],
 ['Robot 1',f"{S['E3_normal_T'][0]['T_offset_m2']:+.8f}",f"{S['E3_normal_T'][0]['T_spread_m2']:+.3e}"],
 ['Robot 2',f"{S['E3_normal_T'][2]['T_offset_m2']:+.8f}",f"{S['E3_normal_T'][2]['T_spread_m2']:+.3e}"]], [150,178,179])
add('两个机器人的相反摆位交互主要来自平均偏移变化；波动项对T的贡献在1e-6 m²量级及以下。数值分解与既有240行MSE核对，最大差异小于2e-16 m²。')
add('可用于论文的英文表述','h')
add('The opposing placement interactions are dominated by changes in the squared mean error rather than within-window fluctuations. Removing any one recording preserves the interaction sign for both robots and both coupling strengths. These findings describe the measured-reference errors in the evaluated static windows.','en')

story.append(PageBreak())
add('历史双车：扩展到已有运动条件','title')
figure('E2_historical_calibration_change.png',507)
add('图3. 三次历史双车记录，依次为Robot 2运动、Robot 1运动及双车运动。每个C均由同一记录原有末五状态的逐时刻MSE重算。红圆是校正Robot 2，橙三角是分别校正两车。','small')
add('Robot 2：仅校正其墙测距时','h')
table([['记录','原始 D (m²)','校正 D (m²)','C (m²)'],
 *[[f'E2-{i+1}',f"{r['D_raw_m2']:+.5f}",f"{r['D_corrected_m2']:+.5f}",f"{r['C_m2']:+.5f}"]
 for i,r in enumerate([r for r in S['E2_contrasts'] if r['car']=='car2' and r['corrected_profile']=='car2_p1_only'])]], [90,139,139,139])
add('前两次记录中，Robot 2的D从负变正，同时Independent与Cooperative的绝对MSE都下降。第三次记录出现相反的排序变化；它保留了条件依赖性，也说明不能把“所有条件同号”设为纳入标准。')
add('本轮核实与后续实验的界线','h')
add('原端点指标是末五状态的坐标中位数到参考点的距离；新指标直接计算这五个时刻的误差平方均值，未把旧端点距离平方冒充MSE。原有端点值全部精确复现。')
add('本轮完成的是已存轨迹的统一指标复算，没有重新拟合定位器。E2仍是批处理车体系模型，E3是静态天线系固定窗模型，二者保留各自身份，不汇总为同一总体统计。')
add('下一步若进行严格统一重放，应使用原始接收事件、适用于运动的固定窗适配器、冻结安装和初始化设置，并保留共同停靠窗口。静态确认适配器会拒绝运动里程计，不能直接套用。历史新摆位及跨天校准分析按116行清单逐项推进。','small')
add('检查结果：4500行共同采样点、240组误差分解、80次剔除、36组历史MSE、12组历史校准变化均通过独立数值读回。','small')

doc=SimpleDocTemplate(str(OUT/'UWB_Cross_Recording_Evidence_Review_20261104.pdf'),pagesize=A4,
 rightMargin=44,leftMargin=44,topMargin=48,bottomMargin=44,
 title='UWB Cross-Recording Evidence Review',author='UWB Cooperative Localization Project')
doc.build(story,onFirstPage=header,onLaterPages=header)

english='''Candidate subsection: Cross-Recording Variability and Calibration Transfer

Recording influence. Removing each of the ten static confirmation recordings
in turn preserves the opposing placement-interaction signs. For full
cooperation, the leave-one-recording-out ranges are [0.08023, 0.08157] m^2 for
robot 1 and [-0.14251, -0.13476] m^2 for robot 2. The corresponding reduced-
coupling ranges also retain their signs. These ranges describe sensitivity to
individual recordings; they are not sampling confidence intervals.

Error components. Each finite-window MSE is decomposed into the squared mean
error and the mean squared deviation about that mean, using a divisor of N.
Across all 120 recording/profile/robot/method combinations in the normal
windows, the squared mean error accounts for more than 99.01% of MSE. The
opposing placement interactions are consequently dominated by changes in mean
offset rather than within-window fluctuations. Both components are relative
to the measured position reference.

Historical extension. The three historical two-robot recordings are remeasured
using epoch-wise MSE on their original, common five-state endpoint windows.
When robot 2's wall ranges are calibrated, its D changes from -0.04095 to
+0.02511 m^2 in E2-1 and from -0.00101 to +0.00970 m^2 in E2-2, although both
estimators' absolute MSEs decrease. E2-3 exhibits the opposite ordering change.
These nominal comparisons extend the observation across the recorded motion
conditions while retaining the historical batch estimator and its calibration
profiles. They are reported separately from the dedicated fixed-lag study.

Chronology scope. Acquisition-order plots retain all ten confirmation
recordings and their actual time spacing. Because placement A precedes B,
the current sequence does not independently identify temporal and placement
effects. We therefore report cross-recording variability without treating
within-recording time blocks as independent acquisition sessions.

Figure caption: E3_calibration_change_chronology
Calibration-induced change C_i for all ten static confirmation recordings in
their normal windows, ordered by acquisition time. Each point is one recording.
The shaded region identifies placement B. Positive C_i indicates a reduction in
the relative cooperative advantage after calibration. Placement and acquisition
order are coupled in this sequence.

Figure caption: E3_mean_offset_and_spread
Finite-window MSE components, averaged with equal weight across recordings
within each placement. Blue squares show the squared mean error relative to
the measured position; orange circles show the centered within-window spread.
The logarithmic ordinate displays their different magnitudes. I, C, and R
denote Independent, Cooperative, and Reduced, respectively.

Figure caption: E2_historical_calibration_change
Calibration-induced change C_i in the three historical two-robot recordings.
All values use epoch-wise MSE on the archived common five-state endpoint
windows. Both predefined calibration profiles are retained. The historical
batch estimates are evaluated separately from the dedicated fixed-lag study.
'''
(OUT/'Paper_Ready_Paragraphs_and_Captions_EN.txt').write_text(english,encoding='utf-8')
print(OUT/'UWB_Cross_Recording_Evidence_Review_20261104.pdf')
