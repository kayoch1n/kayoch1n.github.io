---
layout: post
title:  "Python实现拓扑排序"
date:   2020-03-22 23:42:38 +0800
---

## Code

[leetcode](https://leetcode.com/problems/course-schedule-ii/)

```python
from functools import reduce
from collections import defaultdict, OrderedDict


def sorted(edges):
    """
    https://www.geeksforgeeks.org/topological-sorting/

    :param edges:
    :return:
    """
    adjacent = defaultdict(set)

    for parent, child in edges:
        adjacent[parent].add(child)

    result = OrderedDict()
    seen = list()

    def dfs(p):
        if p in seen:
            raise ValueError('Cycle detected.')

        if p not in result:
            seen.append(p)
            for c in adjacent[p]:
                dfs(c)
            result[p] = p
            seen.pop()

    for c in list(adjacent):
        dfs(c)

    return list(reversed(result.keys()))
```
