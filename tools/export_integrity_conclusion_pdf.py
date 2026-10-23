#!/usr/bin/env python3
"""Render the reviewed numerical findings as one A4 Chinese conclusion page."""
import argparse
import json
from pathlib import Path
import unicodedata
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties


def wrap(text,width=100):
    lines=[];line='';count=0
    for char in text:
        amount=2 if unicodedata.east_asian_width(char) in 'WF' else 1
        if count+amount>width:lines.append(line);line='';count=0
        line+=char;count+=amount
    if line:lines.append(line)
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--results',type=Path,required=True);args=parser.parse_args()
    results=args.results;summary=json.loads((results/'scenario_summary.json').read_text())
    font=FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
    fig=plt.figure(figsize=(8.27,11.69));fig.patch.set_facecolor('white')
    fig.text(.075,.947,'定位完好性监测可行性试验：首轮结论',fontproperties=font,fontsize=17)
    fig.text(.075,.913,'单车 / 固定20秒窗口 / 仿真阈值冻结 / v1.1（保留v1失败）',fontproperties=font,fontsize=10,color='#555555')
    intro='已完成两份历史包复现、5条正常开发运行、8场景×3新种子诊断；37项单车/监测测试及4项指标测试通过。基线PR37（13aeade4c6b13ffa55b0acfafe65c29136067c0f）运行期间固定。M1/M2只监测，三方法发布位置完全相同。'
    fig.text(.075,.88,wrap(intro),fontproperties=font,fontsize=9.4,va='top',linespacing=1.6)
    labels=['正常','短异常','持续正偏','持续负偏','缓增偏差','相关失配','单锚缺测','仅两锚']
    data=[]
    for name,r in zip(labels,summary):
        detected=f"{r['M1_detections']}/3；{r['M2_detections']}/3" if r['category']=='measurement_fault' else '不作故障检出统计'
        data.append([name,detected,f"{r['M1_unalerted_exceed_0p2_s']:.2f} / {r['M2_unalerted_exceed_0p2_s']:.2f}",f"{r['M1_unavailable_s']:.2f} / {r['M2_unavailable_s']:.2f}"])
    ax=fig.add_axes([.075,.485,.85,.285]);ax.axis('off')
    table=ax.table(cellText=data,colLabels=['各3次独立运行','M1；M2故障内报警','未报警且误差>0.20m\nM1 / M2平均秒数','无法监测\nM1 / M2平均秒数'],cellLoc='center',colWidths=[.16,.29,.31,.24],bbox=[0,0,1,1])
    table.auto_set_font_size(False);table.set_fontsize(8.4)
    for (i,j),cell in table.get_celld().items():
        cell.get_text().set_fontproperties(font);cell.get_text().set_fontsize(8.4)
        cell.set_edgecolor('#bfc4c9');cell.set_linewidth(.5)
        if i==0:cell.set_facecolor('#e8edf2')
    paragraphs=[
        ('发现与漏检','持续±0.30m偏差下，M1虽首次报警，随后会随定位器吸收偏差而停报；M2把未报警越界时间压至0–1.33s，但不修正定位误差。渐增偏差M1三次均未报警，M2约16s后报警。短异常M1报警均在2s异常结束后才可得，M2无故障内状态报警。'),
        ('代价与反例','正常仿真M1无误报，M2一条运行误报13s；持续故障恢复后M2仍报警7–9s。仿真阈值事后用于历史正常完成包005135时，M2在92个状态中报警78次，004023为93/96；无连续真值，不能称误报率，但不能据此直接部署阈值。'),
        ('解释边界','状态时刻与结果可获得时刻分开；后者计入1s等待、触发、实测计算及串行队列，是离线接收时钟模型，未经ROS/车载实时验证。缺测或秩不足明确不可用。全部诊断未超过0.50m，不能据零越界证明该门限有效；不声称PL、概率完好性或认证。'),
        ('下一步','优先测试两车共享墙锚持续故障及共同偏移盲区；随后测试车间链路偏差。双向测距按相关观测处理，避免重复增强置信。先核验墙锚/杆臂/Odom参考并取得独立连续真值，再验证阈值迁移和报警时效。')]
    y=.452
    for title,text in paragraphs:
        fig.text(.075,y,title,fontproperties=font,fontsize=10.1,color='#204d70',va='top')
        lines=wrap(text)
        fig.text(.075,y-.025,lines,fontproperties=font,fontsize=9,va='top',linespacing=1.45)
        y-=.025+.0175*len(lines.splitlines())+.019
    fig.text(.075,.032,'完整证据：REPORT.md、metrics.csv、historical_audit.json、FIGURES.md；失败、源码与输入哈希均保留。',fontproperties=font,fontsize=8,color='#555555')
    fig.savefig(results/'CONCLUSION_ONE_PAGE_ZH.pdf')
    fig.savefig(results/'CONCLUSION_ONE_PAGE_ZH.png',dpi=130)
    plt.close(fig)


if __name__=='__main__':main()
