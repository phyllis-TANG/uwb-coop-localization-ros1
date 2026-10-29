# 执行命令与只读取得

工作目录`/home/ubuntu22/uwb-static-to-method-02-20261029`。现场执行过`git branch --show-current`、`git rev-parse HEAD`、`git status --short`、`df -h /home/ubuntu22`和只读`ps`；没有操作ROS进程。

补算前已提交PREREGISTRATION与analyze.py；运行命令、打包、测试、绘图均见HANDOFF原样记录。日志分别为Git外`stats-v1.log`、`tests-v1.log`，无失败或重跑。目录独占创建（exist_ok=False）；若需复核，不覆盖原输出。

C组从已有缓存提取的实际Python步骤（去除打印完整notes的显示语句；文件筛选/校验/写入相同）：

```python
import json, hashlib, tarfile
from pathlib import Path
root = Path('/home/ubuntu22/uwb-static-to-method-02-20261029-artifacts')
out = root / 'input-v1'
out.mkdir(exist_ok=False)
manifest = json.load(open('docs/field_tests/20261024_25/manifest.json'))
archive = Path('/home/ubuntu22/uwb-two-car-imu-fgo-20261028-artifacts/retrieved-inputs/UWB_field_20261024_25_20261025_071212.tar.gz')
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
assert digest == manifest['assets'][0]['sha256']
names = {Path(x['relative_path']).name: x
         for x in manifest['historical_and_fault_bags']
         if Path(x['relative_path']).name.startswith(('T01_', 'T02_', 'T03_', 'T04_'))}
assert len(names) == 4
with tarfile.open(archive) as tf:
    for member in tf:
        name = Path(member.name).name
        if name in names:
            assert member.isfile()
            data = tf.extractfile(member).read()
            assert hashlib.sha256(data).hexdigest() == names[name]['sha256']
            (out / name).write_bytes(data)
        elif any(name.startswith(b[:-4]) for b in names) and name.endswith(('.txt', '.md', '.sha256')):
            assert member.isfile()
            (out / name).write_bytes(tf.extractfile(member).read())
```

只读取这四个bag成员的载荷；遍历其它tar成员仅检查成员名，不提取/解码其测量。INTAKE.json保存当时摘要及成员身份。没有下载、访问NAS、取得视频或扩大包清单。

后续提交只stage专属两个目录，`git diff --cached --check`后本地commit；允许推送该分支并创建draft PR，不合并。远端不可用时保留本地成果，不重跑分析。
