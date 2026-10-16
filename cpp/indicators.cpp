#include <cmath>
#include <vector>

#ifdef _WIN32
#define EXPORT extern "C" __declspec(dllexport)
#else
#define EXPORT extern "C" __attribute__((visibility("default")))
#endif

static const double NOT_A_NUMBER = std::nan("");

// Simple moving average over `window` values. Like pandas, a window that contains a missing
// price (NaN) gives NaN, and the average recovers once the gap has left the window.
EXPORT void sma(const double* x, int n, int window, double* out) {
    double sum = 0.0;
    int missing = 0;  // NaN values currently inside the window
    for (int i = 0; i < n; ++i) {
        if (std::isnan(x[i])) ++missing; else sum += x[i];
        if (i >= window) {
            if (std::isnan(x[i - window])) --missing; else sum -= x[i - window];
        }
        out[i] = (i >= window - 1 && missing == 0) ? sum / window : NOT_A_NUMBER;
    }
}

// RSI with a simple (not smoothed) average of gains and losses.
// Matches the pandas version used by the RSI strategy.
EXPORT void rsi(const double* x, int n, int period, double* out) {
    for (int i = 0; i < n; ++i) out[i] = NOT_A_NUMBER;

    double gain_sum = 0.0, loss_sum = 0.0;
    int missing = 0;  // NaN changes currently inside the window (a missing price makes two of them)
    for (int i = 1; i < n; ++i) {
        double d = x[i] - x[i - 1];
        if (std::isnan(d)) {
            ++missing;
        } else {
            gain_sum += d > 0 ? d : 0.0;
            loss_sum += d < 0 ? -d : 0.0;
        }

        if (i > period) {  // drop the change that just left the window
            double old = x[i - period] - x[i - period - 1];
            if (std::isnan(old)) {
                --missing;
            } else {
                gain_sum -= old > 0 ? old : 0.0;
                loss_sum -= old < 0 ? -old : 0.0;
            }
        }

        if (i >= period && missing == 0) {
            if (loss_sum < 1e-12) {
                out[i] = (gain_sum < 1e-12) ? NOT_A_NUMBER : 100.0;
            } else {
                out[i] = 100.0 - 100.0 / (1.0 + gain_sum / loss_sum);
            }
        }
    }
}

// Rolling extreme using a monotonic queue: O(n) no matter how large the window is.
// is_max = 1 for the highest value, 0 for the lowest.
static void rolling_extreme(const double* x, int n, int window, double* out, bool is_max) {
    std::vector<int> queue(n > 0 ? n : 1);  // indices of candidate extremes
    int head = 0, tail = 0;
    int last_nan = -1000000000;  // index of the latest missing price
    for (int i = 0; i < n; ++i) {
        if (std::isnan(x[i])) {  // like pandas: any window with a missing price gives NaN
            last_nan = i;
            out[i] = NOT_A_NUMBER;
            continue;
        }
        // drop candidates that can never be the extreme again
        while (tail > head && (is_max ? x[queue[tail - 1]] <= x[i] : x[queue[tail - 1]] >= x[i])) --tail;
        queue[tail++] = i;
        // drop the candidates that left the window
        while (queue[head] <= i - window) ++head;
        out[i] = (i >= window - 1 && i - last_nan >= window) ? x[queue[head]] : NOT_A_NUMBER;
    }
}

// Highest value of the last `window` prices (including the current one).
EXPORT void rolling_max(const double* x, int n, int window, double* out) {
    rolling_extreme(x, n, window, out, true);
}

// Lowest value of the last `window` prices (including the current one).
EXPORT void rolling_min(const double* x, int n, int window, double* out) {
    rolling_extreme(x, n, window, out, false);
}