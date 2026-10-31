//! Memoised symmetric distance matrix over a small node set.

use crate::layout::LocId;
use crate::oracle::DistanceOracle;

/// Looks up every unordered pair of `nodes` exactly once (`n * (n - 1) / 2` lookups).
pub(crate) struct DistMatrix {
    n: usize,
    d: Vec<u32>,
}

impl DistMatrix {
    pub(crate) fn build(oracle: &DistanceOracle, nodes: &[LocId]) -> DistMatrix {
        let n = nodes.len();
        let mut d = vec![0u32; n * n];
        for i in 0..n {
            for j in (i + 1)..n {
                let v = oracle.dist(nodes[i], nodes[j]);
                d[i * n + j] = v;
                d[j * n + i] = v;
            }
        }
        DistMatrix { n, d }
    }

    #[inline]
    pub(crate) fn get(&self, i: usize, j: usize) -> u32 {
        self.d[i * self.n + j]
    }
}
