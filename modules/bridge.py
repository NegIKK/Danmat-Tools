import math
import mathutils
import bmesh

# ==============================================================================
# ВПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (ИЗМЕРЕНИЯ И СВЯЗНОСТЬ)
# ==============================================================================

def _edgekey(edge):
    return tuple(sorted([edge.verts[0].index, edge.verts[1].index]))


def get_input(bm, edges=None):
    """Формирует замкнутые или незамкнутые цепочки вершин (loops) из выделенных эджей."""
    target_e = edges if edges else bm.edges
    selected_edges = [_edgekey(edge) for edge in target_e if edge.select and not edge.hide and _edgekey(edge)]
    return _get_connected_selections(selected_edges)


def _get_connected_selections(edge_keys):
    vert_verts = {}
    for ek in edge_keys:
        for i in range(2):
            if ek[i] in vert_verts:
                vert_verts[ek[i]].append(ek[1 - i])
            else:
                vert_verts[ek[i]] = [ek[1 - i]]

    loops = []
    while len(vert_verts) > 0:
        loop = [iter(vert_verts.keys()).__next__()]
        growing = True
        flipped = False

        while growing:
            if loop[-1] not in vert_verts:
                if not flipped:
                    loop.reverse()
                    flipped = True
                else:
                    growing = False
            else:
                extended = False
                for i, next_vert in enumerate(vert_verts[loop[-1]]):
                    if next_vert not in loop:
                        vert_verts[loop[-1]].pop(i)
                        if len(vert_verts[loop[-1]]) == 0:
                            del vert_verts[loop[-1]]
                        if next_vert in vert_verts:
                            if len(vert_verts[next_vert]) == 1:
                                del vert_verts[next_vert]
                            else:
                                vert_verts[next_vert].remove(loop[-1])
                        loop.append(next_vert)
                        extended = True
                        break
                if not extended:
                    if not flipped:
                        loop.reverse()
                        flipped = True
                    else:
                        growing = False

        if loop[0] in vert_verts:
            if loop[-1] in vert_verts[loop[0]]:
                if len(vert_verts[loop[0]]) == 1:
                    del vert_verts[loop[0]]
                else:
                    vert_verts[loop[0]].remove(loop[-1])
                if len(vert_verts[loop[-1]]) == 1:
                    del vert_verts[loop[-1]]
                else:
                    vert_verts[loop[-1]].remove(loop[0])
                loop = [loop, True]
            else:
                loop = [loop, False]
        else:
            loop = [loop, False]

        loops.append(loop)

    return loops


def calculate_lines(bm, loops, mode='shortest', twist=0, reverse=False):
    """Вычисляет пары вершин между двумя лупами для проведения соединительных линий."""
    lines = []
    bm.verts.ensure_lookup_table()
    
    loop1, loop2 = [i[0] for i in loops]
    loop1_circular, loop2_circular = [i[1] for i in loops]
    circular = loop1_circular or loop2_circular
    circle_full = False

    centers = []
    for loop in [loop1, loop2]:
        center = mathutils.Vector()
        for vertex in loop:
            center += bm.verts[vertex].co
        center /= len(loop)
        centers.append(center)
        
    for i, loop in enumerate([loop1, loop2]):
        for vertex in loop:
            if bm.verts[vertex].co == centers[i]:
                centers[i] += mathutils.Vector((0.01, 0, 0))
                break
    center1, center2 = centers

    normals = []
    normal_plurity = False
    for i, loop in enumerate([loop1, loop2]):
        mat = mathutils.Matrix(((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
        x, y, z = centers[i]
        for loc in [bm.verts[vertex].co for vertex in loop]:
            mat[0][0] += (loc[0] - x) ** 2
            mat[1][0] += (loc[0] - x) * (loc[1] - y)
            mat[2][0] += (loc[0] - x) * (loc[2] - z)
            mat[0][1] += (loc[1] - y) * (loc[0] - x)
            mat[1][1] += (loc[1] - y) ** 2
            mat[2][1] += (loc[1] - y) * (loc[2] - z)
            mat[0][2] += (loc[2] - z) * (loc[0] - x)
            mat[1][2] += (loc[2] - z) * (loc[1] - y)
            mat[2][2] += (loc[2] - z) ** 2
            
        normal = False
        if sum(mat[0]) < 1e-6 or sum(mat[1]) < 1e-6 or sum(mat[2]) < 1e-6:
            normal_plurity = True
        try:
            mat.invert()
        except Exception:
            if sum(mat[0]) == 0:
                normal = mathutils.Vector((1.0, 0.0, 0.0))
            elif sum(mat[1]) == 0:
                normal = mathutils.Vector((0.0, 1.0, 0.0))
            elif sum(mat[2]) == 0:
                normal = mathutils.Vector((0.0, 0.0, 1.0))
        if not normal:
            itermax, iter_cnt = 500, 0
            vec = mathutils.Vector((1.0, 1.0, 1.0))
            vec2 = (mat @ vec) / (mat @ vec).length
            while vec != vec2 and iter_cnt < itermax:
                iter_cnt += 1
                vec = vec2
                vec2 = mat @ vec
                if vec2.length != 0:
                    vec2 /= vec2.length
            if vec2.length == 0:
                vec2 = mathutils.Vector((1.0, 1.0, 1.0))
            normal = vec2
        normals.append(normal)

    if ((center1 + normals[0]) - center2).length < ((center1 - normals[0]) - center2).length:
        normals[0].negate()
    if ((center2 + normals[1]) - center1).length > ((center2 - normals[1]) - center1).length:
        normals[1].negate()

    axis = normals[0].cross(normals[1])
    axis = mathutils.Vector([loc if abs(loc) > 1e-8 else 0 for loc in axis])
    if axis.angle(mathutils.Vector((0, 0, 1)), 0) > 1.5707964:
        axis.negate()
    angle = normals[0].dot(normals[1])
    rotation_matrix = mathutils.Matrix.Rotation(angle, 4, axis)

    if circular:
        if loop2_circular and not loop1_circular:
            loop1_circular, loop2_circular = True, False
            loop1, loop2 = loop2, loop1

        target_vector = bm.verts[loop2[0]].co - center2
        dif_angles = [[(rotation_matrix @ (bm.verts[vertex].co - center1)).angle(target_vector, 0), False, i]
                      for i, vertex in enumerate(loop1)]
        dif_angles.sort()
        if len(loop1) != len(loop2):
            angle_limit = dif_angles[0][0] * 1.2
            dif_angles = [[(bm.verts[loop2[0]].co - bm.verts[loop1[index]].co).length, angle, index]
                          for angle, distance, index in dif_angles if angle <= angle_limit]
            dif_angles.sort()
        loop1 = loop1[dif_angles[0][2]:] + loop1[:dif_angles[0][2]]

    if normal_plurity and not circular:
        second_to_first, second_to_second, second_to_last = [(bm.verts[loop1[1]].co - center1).angle(bm.verts[loop2[i]].co - center2) for i in [0, 1, -1]]
        last_to_first, last_to_second = [(bm.verts[loop1[-1]].co - center1).angle(bm.verts[loop2[i]].co - center2) for i in [0, 1]]
        if (min(last_to_first, last_to_second) * 1.1 < min(second_to_first, second_to_second)) or (loop2_circular and second_to_last * 1.1 < min(second_to_first, second_to_second)):
            loop1.reverse()
            if circular:
                loop1 = [loop1[-1]] + loop1[:-1]
    else:
        ang = (bm.verts[loop1[0]].co - center1).cross(bm.verts[loop1[1]].co - center1).angle(normals[0], 0)
        target_angle = (bm.verts[loop2[0]].co - center2).cross(bm.verts[loop2[1]].co - center2).angle(normals[1], 0)
        limit = 1.5707964
        if not ((ang > limit and target_angle > limit) or (ang < limit and target_angle < limit)):
            loop1.reverse()
            if circular:
                loop1 = [loop1[-1]] + loop1[:-1]
        elif normals[0].angle(normals[1]) > limit:
            loop1.reverse()
            if circular:
                loop1 = [loop1[-1]] + loop1[:-1]

    first_to_first, first_to_last = [(bm.verts[loop1[0]].co - center1).angle(bm.verts[loop2[i]].co - center2) for i in [0, -1]]
    if first_to_first > first_to_last:
        loop1.reverse()

    if len(loop1) == len(loop2):
        if twist:
            if abs(twist) < len(loop1):
                loop1 = loop1[twist:] + loop1[:twist]
        if reverse:
            loop1.reverse()

        lines.append([loop1[0], loop2[0]])
        for i in range(1, len(loop1)):
            lines.append([loop1[i], loop2[i]])

    else:
        if len(loop2) > len(loop1):
            loop1, loop2 = loop2, loop1
            loop1_circular, loop2_circular = loop2_circular, loop1_circular

        if twist:
            if abs(twist) < len(loop1):
                loop1 = loop1[twist:] + loop1[:twist]
        if reverse:
            loop1.reverse()

        if loop1_circular and not loop2_circular:
            shifting = 1
            while shifting:
                if len(loop1) - shifting < len(loop2):
                    break
                to_last, to_first = [(rotation_matrix @ (bm.verts[loop1[-1]].co - center1)).angle((bm.verts[loop2[i]].co - center2), 0) for i in [-1, 0]]
                if to_first < to_last:
                    loop1 = [loop1[-1]] + loop1[:-1]
                    shifting += 1
                else:
                    break

        if mode == 'basic':
            lines.append([loop1[0], loop2[0]])
            for i in range(1, len(loop1)):
                if i >= len(loop2) - 1:
                    lines.append([loop1[i], loop2[-1]])
                else:
                    lines.append([loop1[i], loop2[i]])
        else:
            lines.append([loop1[0], loop2[0]])
            prev_vert2 = 0
            for i in range(len(loop1) - 1):
                if prev_vert2 == len(loop2) - 1 and not loop2_circular:
                    tri, quad = 0, 1
                elif prev_vert2 == len(loop2) - 1 and loop2_circular:
                    tri, quad = [(bm.verts[loop1[i + 1]].co - bm.verts[loop2[j]].co).length for j in [prev_vert2, 0]]
                    circle_full = 2
                elif len(loop1) - 1 - i == len(loop2) - 1 - prev_vert2 and not circle_full:
                    tri, quad = 1, 0
                else:
                    tri, quad = [(bm.verts[loop1[i + 1]].co - bm.verts[loop2[j]].co).length for j in range(prev_vert2, prev_vert2 + 2)]

                if tri < quad:
                    lines.append([loop1[i + 1], loop2[prev_vert2]])
                    if circle_full == 2:
                        circle_full = False
                elif not circle_full:
                    lines.append([loop1[i + 1], loop2[prev_vert2 + 1]])
                    prev_vert2 += 1
                else:
                    lines.append([loop1[i + 1], loop2[0]])
                    prev_vert2 = 0
                    circle_full = True

    if loop1_circular and loop2_circular:
        lines.append([loop1[0], loop2[0]])

    return lines


# ==============================================================================
# НАДЁЖНАЯ НАРЕЗКА СЕТКИ МЕЖДУ ПАРАМИ ВЕРШИН
# ==============================================================================

def _connect_vert_pair_safe(bm, v1, v2):
    """
    Безопасное соединение двух вершин:
    1. Пробует стандартное прямое соединение.
    2. Если вершины на разных гранях — ищет путь по смежным граням и соединяет их последовательно.
    """
    if v1 == v2:
        return []
        
    # Проверка: существует ли уже эдж между вершинами
    existing_edge = bm.edges.get((v1, v2))
    if existing_edge:
        return [existing_edge]

    # Попытка 1: Напрямую через стандартный оператор (если в пределах одной грани)
    try:
        res = bmesh.ops.connect_vert_pair(bm, verts=[v1, v2])
        return res.get("edges", [])
    except RuntimeError:
        pass

    # Попытка 2: Если прямой разрез не прошел, соединяем кратчайшим путем через общие грани
    common_faces = set(v1.link_faces).intersection(set(v2.link_faces))
    if common_faces:
        # Вершины принадлежат одной грани, но не удалось нарезать стандартно (бывает при сложных N-гонах)
        try:
            res = bmesh.ops.connect_verts(bm, verts=[v1, v2], faces=list(common_faces))
            return res.get("edges", [])
        except RuntimeError:
            return []

    # Попытка 3: Разрез через несколько полигонов по цепочке смежных граней
    # Ищем последовательность полигонов между v1 и v2
    visited_verts = {v1}
    queue = [[v1]]
    path = None

    while queue:
        curr_path = queue.pop(0)
        curr_v = curr_path[-1]

        if curr_v == v2:
            path = curr_path
            break

        for e in curr_v.link_edges:
            other_v = e.other_vert(curr_v)
            if other_v not in visited_verts:
                visited_verts.add(other_v)
                queue.append(curr_path + [other_v])

    if not path or len(path) < 3:
        return []

    # Проходим по пошаговому пути и соединяем вершины поэтапно
    created_edges = []
    for i in range(len(path) - 1):
        step_v1 = path[i]
        step_v2 = path[i + 1]
        
        edge = bm.edges.get((step_v1, step_v2))
        if not edge:
            try:
                res = bmesh.ops.connect_vert_pair(bm, verts=[step_v1, step_v2])
                created_edges.extend(res.get("edges", []))
            except RuntimeError:
                pass
        else:
            created_edges.append(edge)

    return created_edges


# ==============================================================================
# ОСНОВНОЙ ВХОДНОЙ МЕТОД ДЛЯ SMART EDGE
# ==============================================================================

def make_bridge(context, obj, bm, reverse=False, twist=0, mode='shortest'):
    """
    Интегрированное соединение противоположных ребер/цепочек.
    Принимает параметры reverse, twist и mode.
    """
    selected_edges = [e for e in bm.edges if e.select]
    if not selected_edges:
        return False

    # 1. Формируем цепочки/группы
    loops = get_input(bm, selected_edges)
    if len(loops) < 2:
        return False

    # 2. Рассчитываем виртуальные линии соединения с учетом reverse и twist
    lines = calculate_lines(bm, loops, mode=mode, twist=twist, reverse=reverse)
    if not lines:
        return False

    # 3. Безопасно нарезаем ребра
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    created_edges = []

    for v1_idx, v2_idx in lines:
        bm.verts.ensure_lookup_table()
        if v1_idx >= len(bm.verts) or v2_idx >= len(bm.verts):
            continue

        v1 = bm.verts[v1_idx]
        v2 = bm.verts[v2_idx]

        edges = _connect_vert_pair_safe(bm, v1, v2)
        created_edges.extend(edges)

    # 4. Выделяем результат
    if created_edges:
        for e in bm.edges:
            e.select = False
        for e in created_edges:
            if e.is_valid:
                e.select = True

    bmesh.update_edit_mesh(obj.data)
    return True