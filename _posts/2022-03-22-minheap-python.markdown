---
layout: post
title:  "最小堆的Python实现"
date:   2020-03-22 23:42:38 +0800
---

## Code

最小堆是二叉堆的一个例子。在[二叉堆](https://en.wikipedia.org/wiki/Binary_heap)中，父节点的键值总是保持固定的序关系于任何一个子节点的键值：

```python3
import sys
import unittest

MAX_INT = sys.maxsize
MIN_INT = -MAX_INT


class HeapItem(object):
    def __init__(self, heap, index, data, pri=MAX_INT):
        self._data = data
        self._index = index
        self._heap = heap

        self._pri = pri

    @property
    def pri(self):
        return self._pri

    @pri.setter
    def pri(self, value):
        self._pri = value
        self._heap.update(self._index)

    @property
    def data(self):
        return self._data

    def __str__(self):
        return str(self._pri)


class HeapError(Exception):
    pass


class MinHeap(object):
    def __init__(self, iterable=()):
        self.array_heap = [HeapItem(self, 0, None, MIN_INT)]

        for data, pri in iterable:
            self.insert(data, pri)

    def pop(self):
        if len(self.array_heap) > 1:
            self._swap(1, len(self.array_heap)-1)
            data = self.array_heap.pop().data

            self.update(1)
            return data

        else:
            raise HeapError('No item in heap')


    def insert(self, data, pri=None):
        arr = self.array_heap
        index = len(arr)
        arr.append(HeapItem(self, index, data, pri if pri is not None else data))
        self.update(index)

    def _pos_tuple(self, index):
        return index, self.array_heap[index].pri if index < len(self.array_heap) else MAX_INT

    def update(self, index):
        i, arr = index, self.array_heap

        # Getting larger
        while i < len(arr):
            l, r = 2 * i, 2 * i + 1

            t = min(self._pos_tuple(i), self._pos_tuple(l), self._pos_tuple(r), key=lambda p: p[-1])[0]
            if t == i:
                break

            self._swap(i, t)
            i = t

        # Getting smaller
        while True:
            p = index // 2
            if p > 0 and arr[p].pri > arr[index].pri:
                self._swap(p, index)
                index = p

            else:
                break

    def _swap(self, i, j):
        heap = self.array_heap

        a, b = heap[i], heap[j]

        a._index, b._index = j, i
        heap[i], heap[j] = b, a


class MinHeapTest(unittest.TestCase):
    def test_sortedAsc(self):
        src = [4, 3, 9, 7, 6, 0, 2, 1, 5, 8]

        heap = MinHeap()
        for i in src:
            heap.insert(i)

        actual = []
        while True:
            try:
                actual.append(heap.pop())
            except HeapError:
                break

        self.assertEqual(list(sorted(src)), actual, f'src:{src}')


if __name__ == '__main__':
    unittest.main()
```
