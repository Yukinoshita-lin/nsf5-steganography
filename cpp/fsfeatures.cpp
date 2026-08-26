// fsfeatures.cpp —— C++ 特征提取库 (ctypes 调用)
//
// 计算 8bit 灰度图像的盲隐写分析特征:
//   Gn, Gr          RS 分析 正/负掩码常规-奇异缺口
//   Rm Sm Rn Sn     RS 分组计数
//   chi_stat       卡方统计量
//   chi_p          卡方生存函数 p 值 (用不完全伽马)
//   median_p       前缀卡方中位 p (20 分区)
//   diff_entropy   相邻像素差分熵 (0~8)
//   lsb_diff_entropy LSB 位平面差分熵 (0~1)
//
// 编译 (MinGW):
//   g++ -O2 -shared -o fsfeatures.dll fsfeatures.cpp -static
#include <cmath>
#include <cstdint>
#include <cstring>
#include <vector>
#include <numeric>
#include <algorithm>

extern "C" {

// ---------- 不完全伽马(peg-based), 避免外部依赖 ----------
static double gser(double a, double x, int itmax = 200, double eps = 3e-14) {
    if (x <= 0.0) return 0.0;
    double ap = a, sum = 1.0 / a, del = 1.0 / a;
    for (int i = 0; i < itmax; ++i) {
        ap += 1.0;
        del *= x / ap;
        sum += del;
        if (std::fabs(del) < std::fabs(sum) * eps) break;
    }
    return sum * std::exp(-x + a * std::log(x) - std::lgamma(a));
}

static double gcf(double a, double x, int itmax = 200, double eps = 3e-14, double fpmin = 1e-300) {
    double b = x + 1.0 - a;
    double c = 1.0 / fpmin, d = 1.0 / b, h = 1.0 / b;
    for (int i = 1; i <= itmax; ++i) {
        double an = -i * (i - a);
        b += 2.0;
        d = an * d + b;
        if (std::fabs(d) < fpmin) d = fpmin;
        c = b + an / c;
        if (std::fabs(c) < fpmin) c = fpmin;
        d = 1.0 / d;
        double del = d * c;
        h *= del;
        if (std::fabs(del - 1.0) < eps) break;
    }
    return std::exp(-x + a * std::log(x) - std::lgamma(a)) * h;
}

static double gamma_q(double a, double x) {
    return (x < a + 1.0) ? (1.0 - gser(a, x)) : gcf(a, x);
}
static double chi2_sf(double x, double df) {
    return gamma_q(df / 2.0, x / 2.0);
}

// ---------- 特征计算 (单通道 8bit, row 主序) ----------
// idx0..idx2: 输出指针
__declspec(dllexport) void fs_features(
    const unsigned char* img, int W, int H,
    double* out /* 顺序见头注释 */) {

    int N = W * H;

    // 直方图 + 卡方
    std::vector<int64_t> hist(256, 0);
    for (int i = 0; i < N; ++i) hist[img[i]]++;

    // 卡方全图
    double chi_stat = 0.0; int df = 0;
    for (int g = 0; g < 256; g += 2) {
        double e = (double)hist[g], o = (double)hist[g + 1];
        double s = e + o;
        if (s > 0.0) { df++; chi_stat += (e - o) * (e - o) / s; }
    }
    double chi_p = chi2_sf(chi_stat, (double)df);

    // 前缀卡方中位 p (20 分区) —— 与 Python 对齐: end = max(64, N*i/20)
    double median_p = 0.0;
    {
        std::vector<double> ps; ps.reserve(20);
        for (int k = 1; k <= 20; ++k) {
            int end = std::max(64, (int)(N * k / 20.0));
            if (end > N) end = N;
            std::vector<int64_t> c(256, 0);
            for (int i = 0; i < end; ++i) c[img[i]]++;
            double st = 0.0; int d2 = 0;
            for (int g = 0; g < 256; g += 2) {
                double e = (double)c[g], o = (double)c[g + 1], s2 = e + o;
                if (s2 > 0.0) { d2++; st += (e - o) * (e - o) / s2; }
            }
            ps.push_back((d2 > 0) ? chi2_sf(st, (double)d2) : 0.0);
        }
        std::vector<double> sp = ps;
        std::sort(sp.begin(), sp.end());
        median_p = sp[sp.size() / 2];
    }

    // RS 分析 (掩码 M=[0,1,1,0])
    int m = N - (N % 4);
    int64_t Rm = 0, Sm = 0, Rn = 0, Sn = 0;
    for (int i = 0; i < m; i += 4) {
        int g0 = img[i], g1 = img[i + 1], g2 = img[i + 2], g3 = img[i + 3];
        int fg = std::abs(g1 - g0) + std::abs(g2 - g1) + std::abs(g3 - g2);
        // 正掩码 M=[0,1,1,0]: 翻转 1,2 位
        int p0 = g0, p1 = g1 ^ 1, p2 = g2 ^ 1, p3 = g3;
        int fM = std::abs(p1 - p0) + std::abs(p2 - p1) + std::abs(p3 - p2);
        // 负掩码 -M = 1-M = [1,0,0,1]: 翻转 0,3 位
        int n0 = g0 ^ 1, n1 = g1, n2 = g2, n3 = g3 ^ 1;
        int fN = std::abs(n1 - n0) + std::abs(n2 - n1) + std::abs(n3 - n2);
        if (fM > fg) Rm++; else if (fM < fg) Sm++;
        if (fN > fg) Rn++; else if (fN < fg) Sn++;
    }
    double ngrp = (double)(m / 4);
    double Gr = (Rm - Sm) / ngrp;
    double Gn = (Rn - Sn) / ngrp;

    // 差分熵 (行/列)
    {
        std::vector<int64_t> dh(256, 0); int64_t tot = 0;
        for (int r = 0; r < H; ++r) {
            const unsigned char* row = img + (size_t)r * W;
            for (int c = 1; c < W; ++c) { dh[std::abs(row[c] - row[c - 1])]++; tot++; }
        }
        for (int c = 0; c < W; ++c) {
            for (int r = 1; r < H; ++r) {
                const unsigned char* a = img + (size_t)(r - 1) * W + c;
                const unsigned char* b = img + (size_t)r * W + c;
                dh[std::abs((int)*a - (int)*b)]++; tot++;
            }
        }
        double ent = 0.0;
        for (int g = 0; g < 256; ++g) if (dh[g] > 0) {
            double p = (double)dh[g] / (double)tot;
            ent -= p * std::log2(p);
        }
        out[7] = ent;
    }

    // LSB 位平面差分熵
    {
        std::vector<int64_t> dh2(2, 0); int64_t tot2 = 0;
        for (int r = 0; r < H; ++r) {
            const unsigned char* row = img + (size_t)r * W;
            for (int c = 1; c < W; ++c) { dh2[std::abs((row[c] & 1) - (row[c - 1] & 1))]++; tot2++; }
        }
        for (int c = 0; c < W; ++c) {
            for (int r = 1; r < H; ++r) {
                unsigned char a = img[(size_t)(r - 1) * W + c] & 1;
                unsigned char b = img[(size_t)r * W + c] & 1;
                dh2[std::abs((int)a - (int)b)]++; tot2++;
            }
        }
        double ent = 0.0;
        for (int g = 0; g < 2; ++g) if (dh2[g] > 0) {
            double p = (double)dh2[g] / (double)tot2;
            ent -= p * std::log2(p);
        }
        out[8] = ent;
    }

    // 输出顺序: 0:Rm 1:Sm 2:Rn 3:Sn 4:Gr 5:Gn 6:chi_p 7:diff_entropy 8:lsb_diff_entropy 9:median_p 10:chi_stat
    out[0] = (double)Rm;     out[1] = (double)Sm;
    out[2] = (double)Rn;     out[3] = (double)Sn;
    out[4] = Gr;             out[5] = Gn;
    out[6] = chi_p;
    out[7] = /* set above */ out[7];
    out[8] = /* set above */ out[8];
    out[9] = median_p;
    out[10] = chi_stat;
}

} // extern "C"