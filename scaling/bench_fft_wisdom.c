/* Time 21cmFAST's FFTs with FFTW_ESTIMATE (USE_FFTW_WISDOM = false) and with saved wisdom.
 *
 *   bench_fft_wisdom WISDOM_DIR NTHREADS REPEAT N [N ...]
 *
 * Built and run by pbs_scripts/bench_fft_wisdom_job.sh, against the FFTW module 21cmFAST
 * is built with. Does what dft_r2c_cube / dft_c2r_cube in 21cmFAST's dft.c do: an in-place
 * 3D r2c, then c2r, FFT of an fftwf_malloc'd N^3 box, each plan made right before its FFT
 * (threads set first) and destroyed right after, with FFTW_ESTIMATE, or with
 * FFTW_WISDOM_ONLY after importing the files 21cmFAST's CreateFFTWWisdoms saves
 * (WISDOM_DIR/{r2c,c2r}_DIM<N>_DIM<N>_NTHREADS<t>). Rounds go estimate, wisdom, estimate,
 * wisdom (all wisdom forgotten in between), so node drift shows up as a difference between
 * rounds of one mode. Memory: 8 N^2 (N/2+1) bytes, 13.5 GB at N = 1500.
 */
#include <fftw3.h>
#include <omp.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static double now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + 1e-9 * t.tv_nsec;
}

static void set_threads(int nt) {  // as set_fftw_threads() in dft.c
    fftwf_init_threads();
    fftwf_plan_with_nthreads(nt);
}

/* One FFT like dft_r2c_cube / dft_c2r_cube; < 0 if there is no plan (wisdom only). */
static double one_fft(int c2r, int n, int nt, fftwf_complex *box, unsigned flag) {
    double t0 = now();
    fftwf_plan p;
    set_threads(nt);
    p = c2r ? fftwf_plan_dft_c2r_3d(n, n, n, box, (float *)box, flag)
            : fftwf_plan_dft_r2c_3d(n, n, n, (float *)box, box, flag);
    if (p == NULL) return -1.0;
    fftwf_execute(p);
    fftwf_destroy_plan(p);
    return now() - t0;
}

static int cmp(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}

static double median(double *v, int k) {
    if (k == 0) return -1.0;
    qsort(v, k, sizeof *v, cmp);
    return k % 2 ? v[k / 2] : 0.5 * (v[k / 2 - 1] + v[k / 2]);
}

int main(int argc, char **argv) {
    if (argc < 5) {
        fprintf(stderr, "usage: %s WISDOM_DIR NTHREADS REPEAT N [N ...]\n", argv[0]);
        return 2;
    }
    const char *dir = argv[1];
    int nt = atoi(argv[2]), rep = atoi(argv[3]), nsizes = argc - 4;
    double *est = calloc(nsizes, sizeof(double)), *wis = calloc(nsizes, sizeof(double));
    const char **note = calloc(nsizes, sizeof(char *));
    double *te = malloc(2 * rep * sizeof(double)), *tw = malloc(2 * rep * sizeof(double));

    omp_set_num_threads(nt);
    printf("%s, %d threads, wisdom from %s, %d r2c+c2r pairs per round\n", fftwf_version, nt, dir,
           rep);
    for (int a = 0; a < nsizes; a++) {
        int n = atoi(argv[4 + a]), ke = 0, kw = 0;
        size_t nk = (size_t)n * n * (n / 2 + 1), j;
        fftwf_complex *box = fftwf_malloc(sizeof(fftwf_complex) * nk);
        float *r = (float *)box, scale = 1.0f / ((float)n * n * n);
        char f_r2c[1200], f_c2r[1200];
        note[a] = "";
        if (box == NULL) {
            note[a] = "out of memory";
            continue;
        }
#pragma omp parallel for
        for (j = 0; j < 2 * nk; j++) r[j] = (float)((j * 2654435761u) % 1000u) * 1e-3f;
        snprintf(f_r2c, sizeof f_r2c, "%s/r2c_DIM%d_DIM%d_NTHREADS%d", dir, n, n, nt);
        snprintf(f_c2r, sizeof f_c2r, "%s/c2r_DIM%d_DIM%d_NTHREADS%d", dir, n, n, nt);
        for (int round = 0; round < 4; round++) {
            int w = round % 2;
            fftwf_cleanup_threads();  // forgets all wisdom, as clean_fftw() in dft.c
            if (w) {
                set_threads(nt);  // the wisdom header depends on the threaded planner
                if (!fftwf_import_wisdom_from_filename(f_r2c) ||
                    !fftwf_import_wisdom_from_filename(f_c2r)) {
                    note[a] = "wisdom files missing or not readable by this FFTW";
                    continue;
                }
            }
            printf("  n=%5d %-8s", n, w ? "wisdom" : "estimate");
            for (int i = 0; i < rep; i++) {
                unsigned flag = w ? FFTW_WISDOM_ONLY : FFTW_ESTIMATE;
                double t1 = one_fft(0, n, nt, box, flag), t2 = one_fft(1, n, nt, box, flag);
                if (t1 < 0 || t2 < 0) {
                    note[a] = "no plan for this size in the wisdom files";
                    break;
                }
                if (w) tw[kw++] = t1 + t2;
                else te[ke++] = t1 + t2;
                printf(" %9.3fs", t1 + t2);
                fflush(stdout);
#pragma omp parallel for
                for (j = 0; j < 2 * nk; j++) r[j] *= scale;  // undo c2r's factor N^3 (not timed)
            }
            printf("\n");
            fflush(stdout);
        }
        est[a] = median(te, ke);
        wis[a] = median(tw, kw);
        fftwf_free(box);
    }
    printf("\n%5s %17s %15s %16s\n", "n", "ESTIMATE r2c+c2r", "wisdom r2c+c2r", "wisdom/ESTIMATE");
    for (int a = 0; a < nsizes; a++) {
        if (wis[a] > 0 && est[a] > 0)
            printf("%5s %16.3fs %14.3fs %16.3f\n", argv[4 + a], est[a], wis[a], wis[a] / est[a]);
        else
            printf("%5s %16.3fs %15s %16s  %s\n", argv[4 + a], est[a], "-", "-", note[a]);
    }
    return 0;
}
