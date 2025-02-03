def dfs(graph, source, stack, visited):
    visited.add(source)

    for neighbour in graph[source]:
        if neighbour not in visited:
            dfs(graph, neighbour, stack, visited)

    stack.append(source)


def tsort(graph):
    stack = []
    visited = set()

    for vertex in graph.keys():
        if vertex not in visited:
            dfs(graph, vertex, stack, visited)

    return stack
