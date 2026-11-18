# 第二轮地面 B

首包位于 runtime/101_wall/。A 读取 geometry.json 和 events.jsonl.gz，字段与第一轮相同。起始调查先验对应 t=1 s，UWB 为原始斜距，odom 为各车局部坐标系中的累计基座位姿 [m,m,rad]。两类消息均保留原始源 ID、纳秒采样和接收时间，按接收顺序释放。包名仅用于选择输入。

从共同基准 f61c02e3aad26709a07940bd9900024ec9a93aa1 上的本分支执行（Python 3.10、NumPy 2.2.6、SciPy 1.15.3）。

```sh
python tools/ground_b_round2/export.py 101 wall
(cd docs/research/ground_b_round2/runtime/101_wall && sha256sum -c SHA256SUMS)
```
