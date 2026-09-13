"""
train_cnn —— 隐写分析 CNN (Xu-Net / Ye-Net) 的训练与评估入口。

存在意义: `thesis/exp/run_cnn_sota.py` 与 `thesis/exp/sota_compare.py` 都要
拿 CNN 与项目自己的手工特征 LGB 基线对比, 但此前本文件不存在 (历史上写过一
版, 因当时解释器无 torch 而崩, 未提交即被删除), 于是"小样本下 53d 手工特征
优于 CNN"这一论断在仓库里没有任何数据支撑。本文件把这条路补上。

⚠ 评测纪律 (隐写分析评估的命门): 划分必须**按源图分组**。同一张源图派生的
干净图 + 4 张含密变体若被分到不同侧, 模型只需记住源图内容就能刷高 AUC —— 那
是源图泄漏, 不是隐写检测能力。所有划分一律走 `split_by_photo()`, 落盘
`thesis/data/sota_cnn_split.json`, 供 LGB 基线复用同一份划分, 保证 CNN 与
手工特征是在**逐图相同**的验证集上比较。

用法(库):  from train_cnn import train_one
用法(CLI): python gpu/train_cnn.py --model xunet --epochs 40 --batch 32 --crop 256
冒烟:      python gpu/train_cnn.py --model xunet --epochs 2 --smoke 200
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
DATA_DIR = os.path.join(HERE, "data")
SPLIT_JSON = os.path.join(PROJ, "thesis", "data", "sota_cnn_split.json")

if HERE not in sys.path:
    sys.path.insert(0, HERE)


# --------------------------------------------------------------------------- #
#  数据
# --------------------------------------------------------------------------- #
def _dataset_paths(name: str):
    """名可带或不带 `imageset_` 前缀: 既接受 "bossbase", 也接受调用方
    (thesis/exp/run_cnn_sota.py) 传的 "imageset_bossbase"。"""
    stem = name if name.startswith("imageset_") else f"imageset_{name}"
    base = os.path.join(DATA_DIR, stem)
    return base + ".npz", base + "_x.npy"


def load_imageset(name: str, cache: bool = True):
    """读取 imageset。自适应两种布局:

      A) x 存在 npz 内   ——  盘上现成的 imageset_bossbase.npz
      B) x 落独立 _x.npy ——  gpu/make_imageset.py 的输出格式

    返回 (x, y, photo_id, meta)。x 尽力返回 memmap: 10000x512x512 uint8 解压
    后是 2.6 GB, 常驻内存会挤掉训练所需的显存/内存预算, 因此首次运行把 x 落
    一份 _x.npy (磁盘 2.6 GB), 之后一律 memmap。
    """
    npz_path, x_path = _dataset_paths(name)
    if not os.path.exists(npz_path):
        raise FileNotFoundError(f"找不到 {npz_path} (可先用 gpu/make_imageset.py 生成)")

    z = np.load(npz_path, allow_pickle=True)
    keys = set(z.files)

    if "x" in keys:
        if cache and os.path.exists(x_path):
            x = np.load(x_path, mmap_mode="r")
            if x.shape[0] != z["y"].shape[0]:
                x = None  # 缓存与元数据不匹配, 重新导出
        if cache and not os.path.exists(x_path):
            print(f"[data] 首次运行: 把 x 导出到 {x_path} (约 "
                  f"{z['x'].nbytes / 1e9:.1f} GB), 之后走 memmap", flush=True)
            np.save(x_path, z["x"])
            x = np.load(x_path, mmap_mode="r")
        elif not cache:
            x = z["x"]
    else:
        if not os.path.exists(x_path):
            raise FileNotFoundError(f"{npz_path} 无 'x' 字段, 且 {x_path} 不存在")
        x = np.load(x_path, mmap_mode="r")

    y = np.asarray(z["y"]).astype(np.int64)
    pid = np.asarray(z["photo_id"]).astype(np.int64)
    meta = z["meta"] if "meta" in keys else None
    if len(y) != x.shape[0]:
        raise ValueError(f"imageset 不一致: x={x.shape[0]} 行, y={len(y)} 行")
    return x, y, pid, meta


def split_by_photo(pid, seed: int = 0, val_frac: float = 0.2,
                   write: str | None = SPLIT_JSON, name: str = ""):
    """按**源图**划分训练/验证。返回 (train_idx, val_idx)。

    同一 photo_id 的全部样本必落同一侧。用自带的 default_rng + permutation
    而不是 sklearn 的 GroupShuffleSplit, 是为了让划分跨 sklearn 版本可复现。
    """
    uniq = np.unique(pid)
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(uniq))
    n_val = int(round(len(uniq) * val_frac))
    val_photos = set(uniq[perm[:n_val]].tolist())
    is_val = np.fromiter((p in val_photos for p in pid), dtype=bool, count=len(pid))
    train_idx = np.flatnonzero(~is_val)
    val_idx = np.flatnonzero(is_val)

    if write:
        # 只写第一次 (同一份划分要被 CNN 与 LGB 共用, 后跑者不得覆盖)
        existing = {}
        if os.path.exists(write):
            try:
                with open(write, "r", encoding="utf-8") as fh:
                    existing = json.load(fh)
            except Exception:
                existing = {}
        key = name or "default"
        if key not in existing:
            existing[key] = {
                "seed": seed, "val_frac": val_frac,
                "n_photos": int(len(uniq)), "n_val_photos": int(n_val),
                "n_train_images": int(len(train_idx)),
                "n_val_images": int(len(val_idx)),
                "val_photo_ids": sorted(int(p) for p in val_photos),
            }
            os.makedirs(os.path.dirname(write), exist_ok=True)
            with open(write, "w", encoding="utf-8") as fh:
                json.dump(existing, fh, indent=2, ensure_ascii=False)
            print(f"[split] 写入 {write} (key={key}, "
                  f"{len(train_idx)} 训练 / {len(val_idx)} 验证)", flush=True)
        else:
            print(f"[split] 复用 {write} 中已有的 key={key}", flush=True)
    return train_idx, val_idx


def crop_positions(H: int, W: int, c: int):
    """验证用 5-crop: 四角 + 中心 (图像恰为 c×c 时退化为单点)。"""
    if H <= c or W <= c:
        return [(0, 0)]
    ys = [0, H - c, (H - c) // 2]
    xs = [0, W - c, (W - c) // 2]
    pts = [(0, 0), (0, W - c), (H - c, 0), (H - c, W - c), ((H - c) // 2, (W - c) // 2)]
    return [p for i, p in enumerate(pts) if p not in pts[:i]]


class TrainCrops:
    """训练集: 每个 epoch 每样本随机位置裁剪 + 水平/垂直翻转。

    不做旋转 —— 旋转会改变残差的方向统计, 破坏 SRM 类高通特征的方向敏感性。
    """

    def __init__(self, x, y, idx, crop: int, seed: int = 0):
        self.x, self.y, self.idx, self.crop = x, y, idx, crop
        self.epoch = 0
        self.seed = seed

    def __len__(self):
        return len(self.idx)

    def set_epoch(self, e: int):
        self.epoch = e

    def __getitem__(self, i):
        import torch
        j = self.idx[i]
        img = np.asarray(self.x[j])
        H, W = img.shape[:2]
        c = self.crop
        # 每个 (epoch, i) 一条独立随机流 → 多进程/单进程结果一致
        rng = np.random.default_rng((self.seed * 1_000_003 + self.epoch * 10007 + i) & 0xFFFFFFFF)
        y0 = rng.integers(0, H - c + 1) if H > c else 0
        x0 = rng.integers(0, W - c + 1) if W > c else 0
        patch = img[y0:y0 + c, x0:x0 + c]
        if rng.random() < 0.5:
            patch = patch[:, ::-1]
        if rng.random() < 0.5:
            patch = patch[::-1, :]
        a = np.ascontiguousarray(patch, dtype=np.float32)
        return torch.from_numpy(a)[None], torch.tensor(float(self.y[j]))


# --------------------------------------------------------------------------- #
#  训练 / 评估
# --------------------------------------------------------------------------- #
def _build(model_name: str, device: str):
    from models import MODEL_ZOO
    if model_name not in MODEL_ZOO:
        raise ValueError(f"未知模型 {model_name!r}; 可选 {sorted(MODEL_ZOO)}")
    return MODEL_ZOO[model_name]().to(device)


def _forward_logits(model, batch):
    import torch
    return model(batch).squeeze(-1)


def evaluate(model, x, y, idx, crop: int, device: str, batch: int = 16,
             tta: bool = True) -> np.ndarray:
    """返回验证样本的含密概率 (5-crop TTA 平均)。"""
    import torch
    from torch.amp import autocast

    model.eval()
    probs = np.zeros(len(idx), dtype=np.float64)
    use_amp = device.startswith("cuda")
    with torch.no_grad():
        for s in range(0, len(idx), batch):
            sel = idx[s:s + batch]
            views, owners = [], []
            for k, j in enumerate(sel):
                img = np.asarray(x[j])
                H, W = img.shape[:2]
                pts = crop_positions(H, W, crop) if tta else [((H - crop) // 2, (W - crop) // 2)]
                for (y0, x0) in pts:
                    views.append(np.ascontiguousarray(img[y0:y0 + crop, x0:x0 + crop],
                                                      dtype=np.float32))
                    owners.append(k)
            t = torch.from_numpy(np.stack(views))[:, None].to(device, non_blocking=True)
            with autocast("cuda", dtype=torch.bfloat16, enabled=use_amp):
                logit = _forward_logits(model, t)
            p = torch.sigmoid(logit.float()).cpu().numpy()
            # 同一张图的多个 view 取平均 logit 再 sigmoid 近似等价于概率平均,
            # 这里直接对概率取均值 (单调变换下排序一致, AUC 不受影响)
            for k in range(len(sel)):
                probs[s + k] = p[[i for i, o in enumerate(owners) if o == k]].mean()
    return probs


def train_one(model_name: str, datas, epochs: int = 40, batch: int = 32,
              crop: int = 256, lr: float = 1e-3, device: str = "cuda",
              num_workers: int = 0, out: str | None = None, seed: int = 0,
              val_frac: float = 0.2, patience: int = 6, smoke: int = 0,
              log_every: int = 1):
    """训练一个 CNN 并返回 (best_val_auc, [每 epoch 的 val AUC])。

    两条验证协议, 不要混用 (产物里也分列存放):
      * `aucs`  —— 每个 epoch 的**单中心裁剪** val AUC。训练期用它做早停与选优,
                    比 5-crop TTA 便宜 5 倍, 否则 40 个 epoch 光验证就把时间翻倍。
      * `best_val_auc` —— 载入最优权重后做的 **5-crop TTA** val AUC, 这是对外
                    报告的抬头数字, 也是写进论文表的那个。

    签名与 `thesis/exp/run_cnn_sota.py` 的关键字调用逐字一致, 改动需同步。
    """
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader
    from sklearn.metrics import roc_auc_score

    if isinstance(datas, str):
        datas = [datas]

    torch.manual_seed(seed)
    np.random.seed(seed)
    if device.startswith("cuda"):
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    xs, ys, pids = [], [], []
    offset = 0
    for k, name in enumerate(datas):
        x, y, pid, _meta = load_imageset(name)
        xs.append(x)
        ys.append(y)
        # 跨数据集偏移 photo_id, 防止不同集的同名 ID 被当成同一源图
        pids.append(pid + offset)
        offset += int(pid.max()) + 1
        print(f"[data] {name}: x={x.shape} clean={(y == 0).sum()} "
              f"stego={(y == 1).sum()} photos={len(np.unique(pid))}", flush=True)

    if len(xs) > 1:
        raise NotImplementedError(
            "多数据集拼接暂未实现 (当前实验只用单集); 如需请先把 imageset 合并成一个 npz")

    y = np.concatenate(ys)
    pid = np.concatenate(pids)
    X = xs[0]

    train_idx, val_idx = split_by_photo(
        pid, seed=seed, val_frac=val_frac, name="+".join(datas))

    if smoke:
        rng = np.random.default_rng(0)
        train_idx = rng.choice(train_idx, size=min(smoke, len(train_idx)), replace=False)
        val_idx = rng.choice(val_idx, size=min(max(smoke // 4, 1), len(val_idx)), replace=False)
        epochs = max(epochs, 1)
        print(f"[smoke] 只取 {len(train_idx)} 训练 / {len(val_idx)} 验证样本", flush=True)

    ds = TrainCrops(X, y, train_idx, crop, seed=seed)
    dl = DataLoader(ds, batch_size=batch, shuffle=True, num_workers=num_workers,
                    drop_last=len(ds) > batch, pin_memory=device.startswith("cuda"))

    model = _build(model_name, device)
    n_par = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"[model] {model_name}: {n_par / 1e6:.2f}M 可训练参数", flush=True)

    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-5)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs, eta_min=lr * 0.01)
    crit = nn.BCEWithLogitsLoss()
    use_amp = device.startswith("cuda")

    best_auc, best_state, aucs, bad = -1.0, None, [], 0
    for ep in range(epochs):
        ds.set_epoch(ep)
        model.train()
        t0, tot, seen = time.time(), 0.0, 0
        for bx, by in dl:
            bx = bx.to(device, non_blocking=True)
            by = by.to(device, non_blocking=True)
            opt.zero_grad(set_to_none=True)
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=use_amp):
                logit = _forward_logits(model, bx)
                loss = crit(logit.float(), by)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            tot += float(loss.detach()) * len(by)
            seen += len(by)
        sched.step()

        p = evaluate(model, X, y, val_idx, crop, device,
                     batch=max(8, batch // 2), tta=False)
        auc = float(roc_auc_score(y[val_idx], p))
        aucs.append(auc)
        flag = ""
        if auc > best_auc:
            best_auc, bad = auc, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            flag = " *"
        else:
            bad += 1
        if log_every and (ep % log_every == 0 or ep == epochs - 1):
            print(f"[{model_name}] epoch {ep + 1:3d}/{epochs}  loss={tot / max(seen, 1):.4f}  "
                  f"val_auc={auc:.4f}  lr={sched.get_last_lr()[0]:.2e}  "
                  f"{time.time() - t0:.0f}s{flag}", flush=True)
        if bad >= patience:
            print(f"[{model_name}] 早停: 连续 {patience} 个 epoch 无提升 "
                  f"(best single-crop={best_auc:.4f})", flush=True)
            break

    # 载入最优权重, 用 5-crop TTA 给出对外报告的数字
    if best_state is not None:
        model.load_state_dict(best_state)
    p_tta = evaluate(model, X, y, val_idx, crop, device,
                     batch=max(8, batch // 2), tta=True)
    best_tta = float(roc_auc_score(y[val_idx], p_tta))

    # 训练集 AUC (同一中心裁剪协议) 是"没收敛"与"过拟合"的分水岭: 训练集也贴在
    # 0.5 说明模型根本没能拟合, 不能报成"CNN 输给手工特征"。取样上限 800 张控制开销。
    tr_sub = train_idx[:min(800, len(train_idx))]
    p_tr = evaluate(model, X, y, tr_sub, crop, device,
                    batch=max(8, batch // 2), tta=False)
    train_auc = float(roc_auc_score(y[tr_sub], p_tr))
    print(f"[{model_name}] 最优权重 5-crop TTA val_auc = {best_tta:.4f} "
          f"(单裁剪选优 {best_auc:.4f}, 训练集 AUC = {train_auc:.4f})", flush=True)

    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        # 一并存验证集逐样本概率: 分档 AUC (按 method/density 切片) 与 bootstrap
        # CI 都要从同一份预测算, 避免事后重跑引入口径差。
        torch.save({"model_name": model_name, "state_dict": model.state_dict(),
                    "best_val_auc": best_tta, "best_val_auc_1crop": best_auc,
                    "train_auc_1crop": train_auc,
                    "aucs": aucs, "seed": seed, "crop": crop, "tta": 5,
                    "val_frac": val_frac, "datas": list(datas),
                    "val_idx": val_idx, "val_prob": p_tta,
                    "val_y": y[val_idx], "val_photo_id": pid[val_idx]}, out)
        print(f"[{model_name}] 已保存 {out}", flush=True)

    return best_tta, aucs


def main():
    ap = argparse.ArgumentParser(description="隐写分析 CNN 训练 (Xu-Net / Ye-Net)")
    ap.add_argument("--model", default="xunet", choices=["xunet", "yenet"])
    ap.add_argument("--datas", default="imageset_bossbase",
                    help="逗号分隔的 imageset 名 (对应 gpu/data/imageset_<NAME>.npz)")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--crop", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--num-workers", type=int, default=0, dest="num_workers")
    ap.add_argument("--out", default="")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--smoke", type=int, default=0,
                    help="只用 N 个训练样本跑通流程 (验证签名与显存)")
    args = ap.parse_args()

    out = args.out or os.path.join(PROJ, "models", f"cnn_{args.model}_bossbase.pt")
    best, aucs = train_one(
        model_name=args.model, datas=args.datas.split(","), epochs=args.epochs,
        batch=args.batch, crop=args.crop, lr=args.lr, device=args.device,
        num_workers=args.num_workers, out=out, seed=args.seed, smoke=args.smoke)
    print(f"\n{args.model}: best_val_auc={best:.4f}  epochs={len(aucs)}", flush=True)


if __name__ == "__main__":
    main()
