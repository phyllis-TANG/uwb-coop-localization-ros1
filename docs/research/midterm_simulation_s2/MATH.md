# 模型与数学合同

状态顺序：[t0.car1.x,y,t0.car2.x,y,...,t5.car2.x,y,(b)]，单位m。B0/B1/B3有24维，B2有25维。6个时刻为PR97 linspace(0,1,6)。good锚点(0,0),(5,0),(5,5),(0,5)；weak锚点(-3,0),(-1,0),(4,0),(6,0)。完整轨迹直接调用锁定design。

墙观测预测h=||p_tc−a_k||+I(c=0,k=0,kind=wall)b；peer预测h=||p_t1−p_t0||+I(kind=peer)b。观测=y_clean+注入量+测量噪声，因子残差r=(h−y)/sigma_r。偏差正号表示量测被增加；B3的有效y=y−注入量。B2对指定六行bias列导数为1/sigma_r，其他行为0。

墙的XY导数为(p−a)/||p−a||；peer对car1为−(p1−p0)/||p1−p0||、对car2为正。运动残差=(p_(t+1,c)−p_(t,c)−observed_delta)/sigma_m，Jacobian相应−I/+I；位置prior仅第一时刻4坐标，残差=(p0−prior_center)/sigma_p。没有bias prior，运动bias导数为0。

所有方法最小化同权重的白化残差平方和。B0删除6个peer残差后两车目标可分离，代码用一次块可分离最小二乘调用，联合停止状态；因此B0运行成功是方法级状态，不把两车算成独立成功次数。没有cross-car运动prior或其他隐式协同。

B2信息矩阵块为[Hxx Hxb; Hbx Hbb]；消去自由bias后位置有效信息Hxx−Hxb Hbb^−1 Hbx，在同一线性化点不多于已知bias信息Hxx。这解释零偏差下估计额外bias会付出信息代价。实际B1/B2最终点可能不同，报告的协方差比不是严格同点Schur定理验证，也不是精度必然排序。

Jacobian按S=diag(1,...,1,.1)右乘缩放，SVD(J S)=U diag(s) V^T。rank使用s>s_max×1e-8。满秩时Cov=S V diag(1/s²) V^T S，秩亏返回null，不使用伪逆把不可见方向写成零方差。不根据残差估计sigma，不加ridge。位置cov迹按6时刻逐车2×2对角块迹取均值。

数据+运动信息（不含prior）和总信息均在最终迭代计算；reference_data_rank在生成真值处离线计算，不进入在线解或停止条件。因局部Jacobian可能在离开共线流形后满秩，最终秩不代表全局可辨识性。共线精确点退化及null covariance见CHECKS的singular_solver_case。

所有评价在全部6时刻：MSE_i=(1/6)sum_t||p_hat_ti−p_true_ti||²；RMSE_i=sqrt(MSE_i)；D_i=MSE_i(method)−MSE_i(B0)。不同方法必须来自同一个配对单元，不用不同seed基线。失败仍记录最后估计，双方成功配对统计单列。无经验覆盖率或保护级。
