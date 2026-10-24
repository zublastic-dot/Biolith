package com.terraformersmc.biolith.impl.biome;

import java.util.Arrays;

/**
 * Reusable bookkeeping for the original depth-first search, with the same
 * 64-frame bound. A nested search must not overwrite its caller's cursors.
 * Modified by Zublastic, 2026-10-24; distributed under the repository LGPL.
 */
public final class SearchTreeTraversalStack<T> {
    private final Object[][] arrays = new Object[64][];
    private final int[] indices = new int[64];
    private int used;
    private boolean acquired;

    public SearchTreeTraversalStack<T> acquire() {
        if (acquired) {
            // Reentrant distance callbacks are unusual; preserve their isolation
            // without retaining an unbounded per-thread pool.
            return new SearchTreeTraversalStack<T>().acquire();
        }
        acquired = true;
        return this;
    }

    public void reset(int depth, T[] array) {
        arrays[depth] = array;
        indices[depth] = 0;
        used = Math.max(used, depth + 1);
    }

    public boolean hasNext(int depth) {
        return indices[depth] < arrays[depth].length;
    }

    @SuppressWarnings("unchecked") // Only arrays of T enter through reset.
    public T next(int depth) {
        return (T) arrays[depth][indices[depth]++];
    }

    public void release() {
        // Do not leave tree/registry objects retained by a worker's ThreadLocal.
        Arrays.fill(arrays, 0, used, null);
        used = 0;
        acquired = false;
    }
}
