// nsf5embed.cpp —— nsF5 / matrix 分块嵌入的 C++ 热路径
//
// Python 端负责: 派生种子、构造置乱块列表(order, 全局像素索引)、
// 编码消息比特、头部/正文池划分。本函数只做逐块伴随式编码,
// 遍历顺序与 ns5_core.py 的 _embed 完全一致。
//
// 编译 (跨平台, 见 Makefile 的 `make cpp`):
//   Windows (MinGW): g++ -std=c++17 -O2 -shared -static -o nsf5embed.dll  nsf5embed.cpp
//   Linux:           g++ -std=c++17 -O2 -shared -fPIC -o nsf5embed.so      nsf5embed.cpp
//   macOS:           g++ -std=c++17 -O2 -shared -fPIC -o nsf5embed.dylib   nsf5embed.cpp
// 本文件除 NS5_EXPORT 外全是标准库, 无 windows.h / 无线程 / 无平台分支。
#include <cstdint>
#include <cstdlib>
#include <algorithm>
#include <vector>

#if defined(_WIN32)
#define NS5_EXPORT __declspec(dllexport)
#else
#define NS5_EXPORT __attribute__((visibility("default")))
#endif


extern "C" {

// 块长 n = 2^p - 1, 因此栈上那些"每系数一个"的数组必须按 p 的上限来定尺寸。
// 它们原先是写死的 8 —— 那只够 p ≤ 3 (n=7)。p=4 时 n=15, 会往栈上多写 7 个
// 元素; p=5 时 n=31, 多写 23 个。这是**已存在于仓库中的既成 bug**: Windows 与
// Linux 上属于未定义行为但恰好没表现出错, macOS arm64 的栈保护直接 abort, 于是
// 只有在真的去编译、运行这个库的平台上才暴露出来。
#define NS5_MAX_P 8
#define NS5_MAX_N 255              // (1 << NS5_MAX_P) - 1
#define NS5_P_OK(p) ((p) >= 1 && (p) <= NS5_MAX_P)

// 汉明校验矩阵列向量: 第 j 列(= 1..n) 的二进制 GF(2)^p 表示
// 预计算一次缓存 (p 上限 8)
static const unsigned char* hamming(int p) {
    static unsigned char cache[9][2048];  // 每个 p 以 r*256 行步长存 p×(n≤255), p≤8
    static bool init[9] = {0};
    if (!init[p]) {
        int n = (1 << p) - 1;
        for (int j = 1; j <= n; ++j)
            for (int r = 0; r < p; ++r)
                cache[p][r * 256 + (j - 1)] = (unsigned char)((j >> r) & 1);
        init[p] = true;
    }
    return cache[p];
}

// 计算若干像素 LSB 的伴随式 s = H·x (mod 2), 输出到 s[p]
static inline void syndrome_calc(const unsigned char* H, const unsigned char* xl, int p, int n, unsigned char* s) {
    for (int r = 0; r < p; ++r) {
        int acc = 0;
        for (int y = 0; y < n; ++y) acc ^= H[r * 256 + y] & xl[y];
        s[r] = (unsigned char)acc;
    }
}

// 找到列 tc: H[:,tc] == d[p]。保证唯一。
static inline int find_col(const unsigned char* H, int p, int n, const unsigned char* d) {
    for (int tc = 0; tc < n; ++tc) {
        bool eq = true;
        for (int r = 0; r < p; ++r) if (H[r * 256 + tc] != d[r]) { eq = false; break; }
        if (eq) return tc;
    }
    return 0;  // 不应到达
}

// method: 0=matrix(LSB 翻转), 1=nsF5(减幅+湿纸)
// c: 整幅通道像素(会被原地修改); order: num_blocks*n 个全局像素索引;
// bits: nbits 个 0/1 (已对齐为 p 的倍数); 复用最前面 min(num_blocks, nbits/p) 块。
NS5_EXPORT void nsf5_debug_first(
    const unsigned char* c, const int* pos, int n, int p,
    const unsigned char* bits, int* s_out, int* tc_out) {
    if (!NS5_P_OK(p) || n < 1 || n > NS5_MAX_N) return;
    static const unsigned char* H = NULL;
    (void)H;
    const unsigned char* Hh = hamming(p);
    unsigned char xl[NS5_MAX_N];
    for (int y = 0; y < n; ++y) {
        int xv = (int)c[pos[y]] - 128;
        xl[y] = (unsigned char)(xv & 1);
    }
    unsigned char s[NS5_MAX_P];
    for (int r = 0; r < p; ++r) {
        int acc = 0;
        for (int y = 0; y < n; ++y) acc ^= Hh[r * 256 + y] & xl[y];
        s[r] = (unsigned char)acc;
    }
    unsigned char m[NS5_MAX_P], d[NS5_MAX_P];
    for (int r = 0; r < p; ++r) m[r] = bits[r];
    for (int r = 0; r < p; ++r) d[r] = s[r] ^ m[r];
    int tc = find_col(Hh, p, n, d);
    for (int r = 0; r < p; ++r) s_out[r] = s[r];
    *tc_out = tc;
    for (int r = 0; r < p; ++r) s_out[p + r] = d[r];
}

NS5_EXPORT void nsf5_embed(
    unsigned char* c, int npix,
    const int* order, int num_blocks,
    int n, int p,
    const unsigned char* bits, int nbits,
    int method) {

    if (!NS5_P_OK(p) || n < 1 || n > NS5_MAX_N) return;
    const unsigned char* H = hamming(p);
    int nblocks_use = std::min(num_blocks, nbits / p);
    unsigned char xl[NS5_MAX_N], s[NS5_MAX_P], m[NS5_MAX_P], d[NS5_MAX_P];

    for (int bi = 0; bi < nblocks_use; ++bi) {
        const int* pos = order + (size_t)bi * n;
        for (int r = 0; r < p; ++r) m[r] = bits[bi * p + r];

        int xv[NS5_MAX_N];
        for (int y = 0; y < n; ++y) {
            xv[y] = (int)c[pos[y]] - 128;
            xl[y] = (unsigned char)(xv[y] & 1);
        }
        syndrome_calc(H, xl, p, n, s);

        // s == m ?
        bool eq = true;
        for (int r = 0; r < p; ++r) if (s[r] != m[r]) { eq = false; break; }
        if (eq) continue;

        for (int r = 0; r < p; ++r) d[r] = s[r] ^ m[r];
        int tc = find_col(H, p, n, d);

        if (method == 0) {
            // matrix: 直接翻转 LSB
            if (tc < n) c[pos[tc]] ^= 1;
        } else {
            // nsF5: 减幅或湿纸
            if (tc < n && std::abs(xv[tc]) > 1) {
                c[pos[tc]] = (unsigned char)std::clamp((int)c[pos[tc]] - (xv[tc] > 0 ? 1 : -1), 0, 255);
            } else {
                // 湿纸: 收集 "干" 列(|x|>1)
                std::vector<int> dry;
                for (int k = 0; k < n; ++k) if (std::abs(xv[k]) > 1) dry.push_back(k);
                bool solved = false;
                // 权重1: 单干列
                for (size_t a = 0; a < dry.size() && !solved; ++a) {
                    int k = dry[a]; bool hit = true;
                    for (int r = 0; r < p; ++r) if (H[r * 256 + k] != d[r]) { hit = false; break; }
                    if (hit) {
                        c[pos[k]] = (unsigned char)std::clamp((int)c[pos[k]] - (xv[k] > 0 ? 1 : -1), 0, 255);
                        solved = true;
                    }
                }
                // 权重2: 干列异或
                for (size_t a = 0; a < dry.size() && !solved; ++a) {
                    int ka = dry[a];
                    for (size_t b = a + 1; b < dry.size() && !solved; ++b) {
                        int kb = dry[b]; bool hit = true;
                        for (int r = 0; r < p; ++r) if ((H[r * 256 + ka] ^ H[r * 256 + kb]) != d[r]) { hit = false; break; }
                        if (hit) {
                            for (int k : {ka, kb})
                                c[pos[k]] = (unsigned char)std::clamp((int)c[pos[k]] - (xv[k] > 0 ? 1 : -1), 0, 255);
                            solved = true;
                        }
                    }
                }
                // 兜底: 翻转目标位 LSB, 使伴随式精确命中 m
                if (!solved && tc < n) c[pos[tc]] ^= 1;
            }
        }
    }
}

// ---- nsf5_permute: 确定性伪随机置换 (splitmix64 + 反向 Fisher-Yates) ----
// 与 Python 侧 ns5_core.permute_index 的 fallback 实现保持逐元素一致,
// 使"嵌入/解码"两端无论如何都能还原。数学与实现均不可变, 否则破坏可逆性。
static inline uint64_t splitmix64(uint64_t* x) {
    uint64_t z = (*x += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

NS5_EXPORT void nsf5_permute(long long total, unsigned long long seed, long long* out) {
    if (total <= 0) return;
    for (long long i = 0; i < total; ++i) out[i] = i;
    uint64_t state = seed;
    for (long long i = total - 1; i > 0; --i) {
        unsigned long long r = splitmix64(&state);
        long long j = (long long)(r % (unsigned long long)(i + 1));
        long long tmp = out[i]; out[i] = out[j]; out[j] = tmp;
    }
}

} // extern "C"