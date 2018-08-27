# Utilities for multidimensional matrix and mask construction
import numpy as np
import mmconv as mmc

def joinl(vals, sep):
    '''join a list of lists using sep_list'''
    if len(vals) == 0: 
        return None 
    j = vals[0]
    for l in vals[1:]:
        j += sep + l
    return j


def joinv(val, rep, sep):
    '''join rep repetitions of val using sep.
    works if val and sep are scalars or lists'''
    return (val + sep) * (rep - 1) + val 


def pad(ary, dim, cnt, val):
    '''append ary along dim with cnt copies of val'''
    assert isinstance(ary, np.ndarray)
    shape = list(ary.shape)
    shape[dim] = cnt
    extra = np.full(shape, val)
    return np.concatenate([ary, extra], axis=dim)

def linidx(shape, index):
    '''calculate the linearized index from a multidimensional
    array of shape.
    For example:
    shape = [2,5,4,6,7]
    index = [1,2,1,3,4]
    returns: 4 + 3 * 7 + 1 * 6 * 7 + 2 * 4 * 6 * 7 + 1 * 5 * 4 * 6 * 7 =
             4 + 7 * (3 + 6 * (1 + 4 * (2 + 5 * (1)))) '''
    assert len(shape) == len(index)
    if len(index) == 1:
        return index[0]
    return index[-1] + shape[-1] * linidx(shape[:-1], index[:-1])



class Fold(object):
    '''implement folding and unfolding between one and multiple
    dimensions'''

    def __init__(self, filter_sz, input_sz, stride, padding, dilation):
        self.ndim = len(filter_sz)
        assert len(input_sz) == self.ndim
        assert len(stride) == self.ndim
        assert len(padding) == self.ndim
        assert len(dilation) == self.ndim

        self._fd = filter_sz
        self._id = input_sz
        self.stride = stride
        self.pad = padding
        self.dilation = dilation


    def _i(self, d):
        '''input width in the d-th dimension (from 0)'''
        if d == 0:
            return self._id[d]
        else:
            sep = self._f(d - 1) - 1
            return joinv(self._i(d - 1), self._id[d], sep)


    def _f(self, d):
        '''filter width in the d-th dimension (from 0)'''
        if d == 0:
            return self._fd[d]
        else:
            sep = self._i(d - 1) - 1
            return joinv(self._f(d - 1), self._fd[d], sep)

    def _k(self, d):
        '''position of the key element in the d-th dimension (from 0)'''
        if d == 0:
            return self._f(d) // 2
        else:
            sep = self._i(d - 1) - 1
            return (self._f(d - 1) + sep) * (self._fd[d] // 2) + self._k(d - 1)


    def _ism(self, d):
        '''spacer mask for the input unfolding'''
        if d == 0:
            return [True] * self._i(d)
        else:
            sep = [False] * (self._f(d - 1) - 1)
            return joinv(self._ism(d - 1), self._id[d], sep)

    def _fsm(self, d):
        '''spacer mask for the filter unfolding'''
        if d == 0:
            return [True] * self._fd[d]
        else:
            sep = [False] * (self._i(d - 1) - 1) 
            return joinv(self._fsm(d - 1), self._fd[d], sep)


    def input_spacer_mask(self):
        m = np.full(self._id, True)
        for d in reversed(range(1, self.ndim)):
            m = pad(m, d, self._fd[d] - 1, False)
        end_idx = [s - 1 for s in self._id]
        print(m.shape)
        print(self._id)
        end = linidx(list(m.shape), end_idx)
        return m.reshape(-1)[:end + 1]


    def unfold_filter(self, filter):
        m = filter
        for d in reversed(range(1, self.ndim)):
            m = pad(m, d, self._id[d] - 1, 0)
        end_idx = [s - 1 for s in filter.shape]
        key_idx = [s // 2 for s in self._fd]
        end = linidx(list(m.shape), end_idx) 
        key = linidx(list(m.shape), key_idx)
        return m.reshape(-1)[:end + 1], key


    def validity_mask(self):
        v = np.array([True])
        for d in range(self.ndim):
            m, _ = mmc.make_mask(self._id[d], self._fd[d], self.stride[d], self.pad[d])
            v = np.concatenate(list(map(lambda b: v & b, m)))
        return v


    def make_matrix(self, filter):
        filter_vals, ki = self.unfold_filter(filter)
        filter_vals = filter_vals.tolist()
        tmp_filter_sz = len(filter_vals)
        is_mask = self.input_spacer_mask()
        tmp_matrix_sz = len(is_mask)
        loff = tmp_matrix_sz - ki - 1
        roff = tmp_matrix_sz - tmp_filter_sz + ki

        lzero, ltrim = max(loff, 0), max(-loff, 0)
        rzero, rtrim = max(roff, 0), max(-roff, 0)

        values = [0] * lzero + filter_vals[ltrim:rtrim if rtrim != 0 else None] + [0] * rzero
        assert len(values) == tmp_matrix_sz * 2 - 1

        cells = []
        for i in reversed(range(tmp_matrix_sz)):
            cells += values[i:i + tmp_matrix_sz]

        tmp_mat = np.array(cells).reshape(tmp_matrix_sz, tmp_matrix_sz)
        mat = tmp_mat[is_mask,:][:,is_mask]
        return mat




