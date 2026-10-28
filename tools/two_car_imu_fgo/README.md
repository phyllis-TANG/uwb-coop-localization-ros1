# 双车20秒 gyro+bias FGO

基准和模型见 [MODEL.md](../../docs/field_tests/20261024_25/two_car_imu_fgo_20261028/MODEL.md)。
M0/M1调用冻结原六维F0；M2/M3复用单车F3，八维联合先验不拆交叉项。
没有质量控制、peer门控、回滚、IMU姿态或加速度因子。

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
python -m unittest discover -s tools/two_car_imu_fgo -p 'test_*.py' -v
python tools/two_car_imu_fgo/batch.py freeze --root /outside/synthetic-v1 --test-log /outside/tests.log
python tools/two_car_imu_fgo/batch.py run --root /outside/synthetic-v1
python tools/two_car_imu_fgo/replay.py --events /outside/events.jsonl.gz --config /outside/config.json --method M3 --output /outside/new-run
```

先测试、提交干净源码再冻结输入/完整40索引，不覆盖或自动重试旧运行。
真实包另冻结conditional_development模型，严格物理分支继续BLOCKED；没有数值来源不能补identity时钟或外参。
独立independent.py不导入在线图/优化器/Jacobian，重积分支持、重算全目标和有限差分8维Schur。
