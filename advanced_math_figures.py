"""Bounded, trusted exam-depth constructions. Never executes model-written code."""
from __future__ import annotations
import math, random
import sympy as s
import numpy as np

def _checked(actual, expected):
    if not math.isclose(float(actual), float(expected), rel_tol=2e-08, abs_tol=2e-08):
        raise ValueError('Independent construction check disagreed.')

def _quad2(function, left, right, low, high):
    nodes, weights = np.polynomial.legendre.leggauss(14)
    total = 0.0
    for n, w in zip(nodes, weights):
        x = (right - left) * (n + 1) / 2 + left
        lo, hi = (low(x), high(x))
        total += w * sum((v * function(x, (hi - lo) * (m + 1) / 2 + lo) * (hi - lo) / 2 for m, v in zip(nodes, weights))) * (right - left) / 2
    return total

def _part(label, value, requirement):
    from answer_parts import SolvedPart, evaluate_parts
    if isinstance(value, (tuple, list, s.MatrixBase)):
        return SolvedPart(label=label, kind='symbolic', answer=s.latex(s.Matrix(value)), requirements=requirement)
    if isinstance(value, s.Tuple):
        return SolvedPart(label=label, kind='symbolic', answer=s.latex(value), requirements=requirement)
    exact = s.simplify(value)
    if exact.is_number:
        return evaluate_parts([SolvedPart(label=label, kind='numeric', expression=str(float(exact)), requirements=requirement)])[0]
    return SolvedPart(label=label, kind='symbolic', answer=s.latex(exact), requirements=requirement)

def _finish(family, title, givens, tasks, answers, working, body, kind, rng, unit='', difficulty=None):
    from tools import QuestionDraft
    from math_figures import MathFigure, _svg
    from answer_parts import canonical_from_parts
    if difficulty == 'insane':
        final = answers[-1][-1] if isinstance(answers[-1], (tuple, list, s.Tuple)) else answers[-1]
        focused = {'double_integral': tasks[-1], 'triple_integral': tasks[-1], 'quadratic': tasks[-1], 'line': 'Find the radius of the circle with diameter PR.', 'triangle': 'Find the ratio of the circumradius of triangle ABD to the inradius of triangle ABC.', 'circle': 'Two possible circle-and-external-point configurations have the same tangent length PT and tangent-triangle area as the reference figure. PA is allowed to change in the second configuration. Find the ratio of the larger circle radius to the smaller one.', 'cuboid': 'Find the ratio of the circumcircle area of right triangle ABG to the square of the shortest surface path from A to G. Consider the possible unfoldings.'}[family]
        if kind == 'long_answer':
            intermediate = {'double_integral': lambda: ('Evaluate the total mass.', answers[1][0]), 'triple_integral': lambda: ('Evaluate the total mass.', answers[1][0]), 'quadratic': lambda: ('Find the coordinates of S.', s.Tuple(*answers[0][1:])), 'line': lambda: ('Determine the positive parameter t.', answers[1]), 'triangle': lambda: ('Find the length AD.', answers[1][-1]), 'circle': lambda: ('Determine the radius of the circle in the figure.', answers[0][-1]), 'cuboid': lambda: ('Find the length of space diagonal AG.', answers[0][-1])}[family]()
            tasks = [intermediate[0], focused]
            answers = [intermediate[1], final]
        else:
            tasks = [focused]
            answers = [final]
    givens += ' The diagram is schematic and not to scale.'
    if len(tasks) != len(answers) or not 1 <= len(tasks) <= 3:
        raise ValueError('Invalid assessment structure.')
    if kind == 'mcq':
        final = answers[-1][-1] if isinstance(answers[-1], (tuple, list, s.Tuple)) else answers[-1]
        target = float(final)
        correct = round(target, 3)
        values = [correct]
        for candidate in [target / 2, target * 2, target + 1, target - 1, target + 2, target - 2]:
            candidate = round(candidate, 3)
            if candidate not in values:
                values.append(candidate)
            if len(values) == 4:
                break
        if len(values) != 4:
            raise ValueError('Ambiguous distractors.')
        rng.shuffle(values)
        options = [f'{v:.3f}'.rstrip('0').rstrip('.') + (' ' + unit if unit else '') for v in values]
        index = values.index(correct)
        key = f"{'ABCD'[index]}. {options[index]}"
        question = givens + ' ' + ' '.join(tasks) + ' Select the final requested numerical value, to 3 decimal places.'
        parts = [_part('answer', final, tasks[-1])]
    else:
        options = []
        parts = [_part('abc'[i], value, task) for i, (task, value) in enumerate(zip(tasks, answers))]
        question = givens + ' Show working and justify your conclusions for each part. Give numerical results to 3 decimal places; exact forms are also accepted.\n\n' + '\n\n'.join((f"({'abc'[i]}) {task}" for i, task in enumerate(tasks)))
        key = '; '.join((f"({'abc'[i]}) ${s.latex(s.Matrix(value) if isinstance(value, (tuple, list)) else value)}$" for i, value in enumerate(answers)))
    alt = givens.replace('$', '') + ' The diagram represents the stated construction; use the givens rather than measuring pixels.'
    figure = MathFigure(family=family, title=title, alt=alt[:1500], svg=_svg(body, title, alt[:1500]), version=2)
    return QuestionDraft(question=question, canonical_answer=key, solution=working + '\nFinal answers: ' + key, question_type=kind, options=options, answer_parts=parts, formula_focus=title, figure=figure.model_dump())

def integration(family, difficulty, kind, seed):
    from math_figures import _line, _text, _path
    rng = random.Random(seed)
    x, y, z, r = s.symbols('x y z r', nonnegative=True)
    insane = difficulty == 'insane'
    if family == 'double_integral':
        a, b, c = (rng.randint(1, 3), rng.randint(2, 4), rng.randint(1, 3))
        X = a * b
        Y = a * b * b
        density = x + c * y
        mass = s.integrate(density, (y, x * x / a, b * x), (x, 0, X))
        moment = s.integrate(x * density, (y, x * x / a, b * x), (x, 0, X))
        centroid = s.simplify(moment / mass)
        reversed_mass = s.integrate(density, (x, y / b, s.sqrt(a * y)), (y, 0, Y))
        _checked(mass, reversed_mass)
        _checked(mass, _quad2(lambda u, v: u + c * v, 0, X, lambda u: u * u / a, lambda u: b * u))
        u, v = s.symbols('u v', nonnegative=True)
        jacobian = abs(s.det(s.Matrix([[s.diff(v, u), s.diff(v, v)], [s.diff(u * v, u), s.diff(u * v, v)]])))
        assert jacobian == v
        transformed = s.integrate((v + c * u * v) * v, (v, 0, a * u), (u, 0, b))
        _checked(mass, transformed)
        fraction = s.simplify(s.integrate(density, (x, y / b, s.sqrt(a * y)), (y, s.Rational(Y, 4), Y)) / mass)
        A = s.Symbol('I_{xy}')
        B = s.Symbol('I_{yx}')
        bounds = f'In y-first order: 0 <= x <= {X}, x^2/{a} <= y <= {b}x. In x-first order: 0 <= y <= {Y}, y/{b} <= x <= sqrt({a}y).'
        setup = s.Integral(density, (y, x * x / a, b * x), (x, 0, X))
        other = s.Integral(density, (x, y / b, s.sqrt(a * y)), (y, 0, Y))
        givens = f'The lamina occupies the bounded region R between $y=x^2/{a}$ and $y={b}x$ in the first quadrant. Its density is $\\rho(x,y)=x+{c}y$.'
        if difficulty in {'easy', 'medium'}:
            tasks = ['Evaluate the mass using an iterated integral.']
            answers = [mass]
        elif insane:
            tasks = ['Set up the mass integral in both integration orders, deriving every boundary.', 'Use $u=y/x$, $v=x$ on the interior to derive the transformed region and Jacobian, then evaluate the mass and the x-coordinate of the centre of mass.', 'Find the fraction of the mass lying above $y=' + str(Y) + '/4$.']
            answers = [s.Tuple(setup, other), s.Tuple(mass, centroid), fraction]
        else:
            tasks = ['Derive both orders of integration for the mass.', 'Evaluate the total mass.', 'Find the x-coordinate of the centre of mass.']
            answers = [s.Tuple(setup, other), mass, centroid]
        body = _line(70, 290, 460, 290) + _line(70, 290, 70, 35) + _text(475, 300, 'x') + _text(60, 25, 'y')
        PX = lambda t: 70 + 350 * t / X
        PY = lambda t: 290 - 220 * t / Y
        points = [(PX(X * i / 100), PY((X * i / 100) ** 2 / a)) for i in range(101)] + [(PX(X * i / 100), PY(b * X * i / 100)) for i in range(100, -1, -1)]
        body += '<polygon points="' + ' '.join((f'{p:.2f},{q:.2f}' for p, q in points)) + '" fill="currentColor" fill-opacity="0.08"/>'
        body += _path(points[:101]) + _line(70, 290, PX(X), PY(Y)) + _text(250, 95, f'y = {b}x') + _text(335, 238, f'y = x²/{a}') + _text(270, 185, 'R')
        _checked(moment,_quad2(lambda u,v:u*(u+c*v),0,X,lambda u:u*u/a,lambda u:b*u))
        working=(f'Intersecting the boundaries gives $x=0$ and $x={X}$, with top height $y={Y}$. '
            f'The mass is $M={s.latex(setup)}={s.latex(mass)}$. ')
        inner_mass=s.integrate(density,(y,x*x/a,b*x))
        mass_primitive=s.integrate(inner_mass,x)
        working+=f'Integrating the inner variable gives $M=\\int_0^{{{X}}}({s.latex(inner_mass)})\\,dx=[{s.latex(mass_primitive)}]_0^{{{X}}}={s.latex(mass)}$. '
        if difficulty=='hard':
            moment_integral=s.Integral(x*density,(y,x*x/a,b*x),(x,0,X))
            working+=(f'For a horizontal slice, $y/{b}\\le x\\le\\sqrt{{{a}y}}$ and $0\\le y\\le {Y}$, '
                f'so the reversed-order integral is ${s.latex(other)}$. '
                f'The first moment is $M_y={s.latex(moment_integral)}={s.latex(moment)}$, '
                f'hence $\\bar x=M_y/M={s.latex(centroid)}$.')
        elif insane:
            partial_integral=s.Integral(density,(x,y/b,s.sqrt(a*y)),(y,s.Rational(Y,4),Y))
            _checked(fraction,_quad2(lambda yy,xx:xx+c*yy,Y/4,Y,lambda yy:yy/b,lambda yy:math.sqrt(a*yy))/float(mass))
            working+=(f'Above the cutoff $y={s.latex(s.Rational(Y,4))}$ the horizontal bounds are '
                f'$y/{b}\\le x\\le\\sqrt{{{a}y}}$. '
                f'That portion has mass ${s.latex(partial_integral)}={s.latex(s.simplify(fraction*mass))}$, '
                f'so its fraction of the total mass is ${s.latex(fraction)}$.')
        return _finish(family, 'Multiple integration region', givens, tasks, answers, working, body, kind, rng, difficulty=difficulty)
    H = rng.randint(3, 6)
    a = rng.randint(1, 2)
    b = a + 1
    p = rng.randint(1, 3)
    L = s.Rational(H, 3) if insane else s.Integer(0)
    outer = z / a
    inner = z / b if insane else s.Integer(0)
    density = z ** p
    mass = s.simplify(2 * s.pi * s.integrate(r * density, (r, inner, outer), (z, L, H)))
    centroid = s.simplify(2 * s.pi * s.integrate(z * r * density, (r, inner, outer), (z, L, H)) / mass)
    median = s.simplify(((s.Integer(H) ** (p + 3) + L ** (p + 3)) / 2) ** s.Rational(1, p + 3))
    coeff = s.pi * (s.Rational(1, a * a) - (s.Rational(1, b * b) if insane else 0))
    _checked(mass, coeff * (s.Integer(H) ** (p + 3) - L ** (p + 3)) / (p + 3))
    _checked(mass, 2 * math.pi * _quad2(lambda zz, rr: rr * zz ** p, float(L), H, lambda zz: float(zz / b) if insane else 0, lambda zz: float(zz / a)))
    _checked(mass, 2 * math.pi * _quad2(lambda ph, rad: (rad * math.cos(ph)) ** p * rad ** 2 * math.sin(ph), math.atan(1 / b) if insane else 0, math.atan(1 / a), lambda ph: float(L) / math.cos(ph), lambda ph: H / math.cos(ph)))
    _checked(coeff * (s.Integer(H) ** (p + 3) - median ** (p + 3)) / (p + 3), mass / 2)
    rr, phi, theta = s.symbols('rho phi theta', nonnegative=True)
    phi0 = s.atan(s.Rational(1, b)) if insane else s.Integer(0)
    phi1 = s.atan(s.Rational(1, a))
    spherical = s.Integral((rr * s.cos(phi)) ** p * rr ** 2 * s.sin(phi), (rr, L / s.cos(phi), H / s.cos(phi)), (phi, phi0, phi1), (theta, 0, 2 * s.pi))
    cylindrical = s.Integral(r * z ** p, (r, inner, outer), (z, L, H), (theta, 0, 2 * s.pi))
    radial = 'between the cones $z=' + str(a) + '\\sqrt{x^2+y^2}$ and $z=' + str(b) + '\\sqrt{x^2+y^2}$' if insane else 'inside the cone $z=' + str(a) + '\\sqrt{x^2+y^2}$'
    givens = f'A solid lies {radial}, with ${s.latex(L)}\\le z\\le {H}$ and density $\\delta(x,y,z)=z^{p}$. Use spherical convention $z=\\rho\\cos\\phi$, $r=\\rho\\sin\\phi$.'
    if difficulty in {'easy', 'medium'}:
        tasks = ['Set up and evaluate the mass in cylindrical coordinates.']
        answers = [mass]
    elif insane:
        tasks = ['Derive cylindrical and spherical mass integrals, including the transformed planar bounds and Jacobians.', 'Evaluate the mass and the z-coordinate of the centre of mass.', 'Find the unique horizontal cut $z=t$ that leaves half the mass above it; justify uniqueness.']
        answers = [s.Tuple(cylindrical, spherical), s.Tuple(mass, centroid), median]
    else:
        tasks = ['Derive cylindrical and spherical mass integrals with all bounds and Jacobians.', 'Evaluate the mass.', 'Find the z-coordinate of the centre of mass.']
        answers = [s.Tuple(cylindrical, spherical), mass, centroid]
    body = _line(260, 315, 260, 35) + _line(260, 315, 420, 335) + _text(245, 28, 'z') + _text(435, 340, 'r')
    body += f'<ellipse cx="260" cy="80" rx="140" ry="32" fill="none" stroke="currentColor" stroke-width="2.5"/>' + _line(120, 80, 260, 315) + _line(400, 80, 260, 315) + _text(85, 85, f'z = {H}')
    if insane:
        body += f'<ellipse cx="260" cy="80" rx="{140 * a / b}" ry="{32 * a / b}" fill="none" stroke="currentColor" stroke-width="2.5" stroke-dasharray="7 5"/>' + _line(260 - 140 * a / b, 80, 260, 315, True) + _line(260 + 140 * a / b, 80, 260, 315, True) + _line(213, 237, 307, 237) + _text(350, 245, f'z = {H}/3')
    _checked(centroid,s.Rational(p+3,p+4)*(s.Integer(H)**(p+4)-L**(p+4))/(s.Integer(H)**(p+3)-L**(p+3)))
    working=f'The radial and height bounds give $M={s.latex(cylindrical)}={s.latex(mass)}$, using cylindrical Jacobian $r$. '
    working+=(f'Radial integration gives $Cz^{{{p+2}}}$ with $C={s.latex(coeff)}$, so '
        f'$M=C({H}^{{{p+3}}}-({s.latex(L)})^{{{p+3}}})/{p+3}={s.latex(mass)}$. ')
    if difficulty=='hard':
        working+=(f'The cone boundaries give polar angles ${s.latex(phi0)}\\le\\phi\\le{s.latex(phi1)}$; the horizontal planes give $\\rho=z/\\cos\\phi$. In spherical coordinates the mass integral is ${s.latex(spherical)}$, '
            'with Jacobian $\\rho^2\\sin\\phi$. '
            f'Weighting the mass integrand by z gives the first moment, so $\\bar z={s.latex(centroid)}$.')
    elif insane:
        power=p+3
        working+=(f'After radial integration the mass density per unit height is $Cz^{{{power-1}}}$ with $C={s.latex(coeff)}$. '
            f'The mass above a cut t is $C({H}^{{{power}}}-t^{{{power}}})/{power}$. '
            f'Equating this to $M/2$ gives $t^{{{power}}}=({H}^{{{power}}}+({s.latex(L)})^{{{power}}})/2$, '
            f'hence $t={s.latex(median)}$. The cumulative mass is strictly increasing inside the positive-density region, so this cut is unique.')

    return _finish(family, 'Solid of integration', givens, tasks, answers, working, body, kind, rng, difficulty=difficulty)

def geometry(family, difficulty, kind, seed):
    from math_figures import _line, _text, _path, _svg, _graph
    rng = random.Random(seed)
    insane = difficulty == 'insane'
    if family == 'quadratic':
        h, k = (rng.randint(1, 3), -rng.randint(2, 6))
        m = rng.choice([2, 4, 6])
        t = s.Rational(m, 2) + h
        c = k - m * h - s.Rational(m * m, 4)
        sy = (t - h) ** 2 + k
        R = s.Point(0, sy + t / m)
        V = s.Point(h, k)
        S = s.Point(t, sy)
        area = abs(s.det(s.Matrix([[S.x - V.x, S.y - V.y], [R.x - V.x, R.y - V.y]]))) / 2
        circle = s.Circle(V, S, R)
        radius = circle.radius
        x = s.Symbol('x')
        poly = s.expand((x - h) ** 2 + k - (m * x + c))
        assert s.discriminant(poly, x) == 0 and s.simplify(poly.subs(x, t)) == 0
        _checked((S - R).dot(s.Point(1, m)), 0)
        given = f'The parabola is $y=(x-{h})^2+({k})$. The line $y={m}x+c$ is tangent at S. V is the turning point. The perpendicular to the tangent through S meets the y-axis at R.'
        tasks = ['Determine c and the coordinates of S.', 'Find R, then the area of triangle VSR.', 'Find the radius of the circle through V, S and R.'] if insane else ['Determine c and the point of tangency S.', 'Find the coordinates of R.', 'Find the area of triangle VSR.']
        answers = [s.Tuple(c, t, sy), s.Tuple(R.x, R.y, area) if insane else s.Tuple(R.x, R.y), radius if insane else area]
        xmin, xmax = (-1, float(t) + 1)
        ymin, ymax = (min(float(R.y), k) - 2, max(float(R.y), float(S.y), k) + 4)
        PX = lambda q: 70 + 370 * (float(q) - xmin) / (xmax - xmin)
        PY = lambda q: 305 - 265 * (float(q) - ymin) / (ymax - ymin)
        points = [(PX(xmin + (xmax - xmin) * i / 120), PY((xmin + (xmax - xmin) * i / 120 - h) ** 2 + k)) for i in range(121)]
        points = [point for point in points if 35 <= point[1] <= 315]
        body = _line(45, PY(0), 475, PY(0)) + _line(PX(0), 320, PX(0), 30) + _path(points)
        for point, label in [(V, 'V'), (S, 'S'), (R, 'R')]:
            body += _text(PX(point.x) + 10, PY(point.y) - 12, label)
        body += _line(PX(R.x), PY(R.y), PX(S.x), PY(S.y))
        working = f'Tangency makes the discriminant zero: c={c}; S=({t},{sy}). A perpendicular gradient is -1/{m}, hence R={R}. Determinant area={area}. The circumcircle of the three noncollinear points has centre {circle.center} and radius {radius}. Dot-product and discriminant checks independently confirm the construction.'
    elif family == 'line':
        a, b = (2, 3)
        u, v = (rng.randint(2, 5), rng.randint(1, 4))
        T = rng.randint(2, 5)
        A = s.Matrix([[a, b], [b, -a]])
        R = A.inv() * s.Matrix([u, v])
        px = s.Rational(u, a)
        qx = s.Rational(v, b)
        basearea = abs((qx - px) * R[1]) / 2
        if basearea == 0:
            return geometry(family, difficulty, kind, (seed or 0) + 23)
        area = s.simplify(basearea * T * T)
        rx, ry = R * T
        distance = s.sqrt(rx ** 2 + ry ** 2)
        target = distance if insane else s.Integer(T)
        given = f'For a positive parameter t, $L_1:{a}x+{b}y={u}t$ and $L_2:{b}x-{a}y={v}t$. Their x-intercepts are P and Q and their intersection is R. The area of triangle PQR is ${s.latex(area)}$.'
        tasks = ['Find R and the intercepts in terms of t, and justify that the lines are perpendicular.', 'Determine t from the area constraint.', 'Find the distance OR and the radius of the circle with diameter PR.'] if insane else ['Find R and both x-intercepts in terms of t.', 'Derive the equation for t using the area constraint.', 'Determine the positive value of t.']
        circum = s.sqrt((rx - px * T) ** 2 + ry ** 2) / 2
        tsym = s.Symbol('t', positive=True)
        answers = [s.Tuple(R[0] * tsym, R[1] * tsym, px * tsym, qx * tsym), s.Integer(T) if insane else s.Tuple(s.Eq(basearea * tsym ** 2, area)), s.Tuple(distance, circum) if insane else target]
        xs = [0, float(px * T), float(qx * T), float(rx)]
        ys = [0, float(ry)]
        xmin, xmax = (min(xs) - 2, max(xs) + 2)
        ymin, ymax = (min(ys) - 2, max(ys) + 2)
        PX = lambda x: 70 + 370 * (float(x) - xmin) / (xmax - xmin)
        PY = lambda y: 300 - 245 * (float(y) - ymin) / (ymax - ymin)
        body = _line(PX(xmin), PY(0), PX(xmax), PY(0)) + _line(PX(0), PY(ymin), PX(0), PY(ymax))
        for function in [lambda xx: (u * T - a * xx) / b, lambda xx: (b * xx - v * T) / a]:
            points = [(PX(xx), PY(function(xx))) for xx in np.linspace(xmin, xmax, 180) if ymin <= function(xx) <= ymax]
            if points:
                body += _path(points)
        for xx, yy, label in [(px * T, 0, 'P'), (qx * T, 0, 'Q'), (rx, ry, 'R')]:
            body += _text(PX(xx) + (-10 if label == 'P' else 10), PY(yy) + (22 if label == 'Q' else -13), label)
        working = f'Intersection R=t({R[0]},{R[1]}), P=({px}t,0), Q=({qx}t,0). The normals have dot product zero. Area={basearea}t²={area}; positivity selects t={T}. OR={distance}; radius of diameter PR={circum}. All coordinates satisfy both line equations.'
    elif family == 'triangle':
        b, c = (s.Integer(rng.randint(6, 11)), s.Integer(rng.randint(4, 9)))
        A = s.Point(0, 0)
        B = s.Point(c, 0)
        C = s.Point(b / 2, b * s.sqrt(3) / 2)
        side = B.distance(C)
        D = s.Point((b * B.x + c * C.x) / (b + c), (b * B.y + c * C.y) / (b + c))
        BD = B.distance(D)
        AD = A.distance(D)
        area = b * c * s.sqrt(3) / 4
        inradius = s.simplify(2 * area / (side + b + c))
        areaABD = s.simplify(c * D.y / 2)
        circum = s.simplify(c * BD * AD / (4 * areaABD))
        ratio = s.simplify(circum / inradius)
        _checked(BD / C.distance(D), c / b)
        _checked(AD, s.sqrt(3) * b * c / (b + c))
        _checked(circum, s.Circle(A, B, D).radius)
        given = f'In triangle ABC, $AB={c}$, $AC={b}$ and $\\angle BAC=60^\\circ$. AD is the internal angle bisector, meeting BC at D.'
        tasks = ['Find BC exactly using a justified method.', 'Determine BD and AD.', 'Find the inradius of ABC, then the ratio of the circumradius of ABD to that inradius.'] if insane else ['Find BC exactly.', 'Determine BD and AD using the angle-bisector relationship.', 'Find the inradius of ABC.']
        answers = [side, s.Tuple(BD, AD), s.Tuple(inradius, ratio) if insane else inradius]
        PX = lambda x: 85 + 30 * float(x)
        PY = lambda y: 300 - 25 * float(y)
        body = _path([(PX(A.x), PY(A.y)), (PX(B.x), PY(B.y)), (PX(C.x), PY(C.y)), (PX(A.x), PY(A.y))]) + _line(PX(A.x), PY(A.y), PX(D.x), PY(D.y))
        for point, label in [(A, 'A'), (B, 'B'), (C, 'C'), (D, 'D')]:
            body += _text(PX(point.x) + 8, PY(point.y) - 12, label)
        body += _text(180, 330, str(c)) + _text(100, 180, str(b)) + _text(143, 275, '60°')
        working = f'Cosine rule gives BC={side}. BD:DC=AB:AC={c}:{b}; BD={BD}. AD² from the coordinate construction gives AD={AD}. Total area={area}; inradius=area/semiperimeter={inradius}. Area ABD={areaABD}; its circumradius is AB·BD·AD/(4 area ABD)={circum}. The requested ratio is {ratio}. Independent coordinate distances, angle-bisector ratio and circumcircle checks agree.'
    elif family == 'circle':
        radius = s.Integer(rng.choice([5, 8, 12]))
        d = radius + rng.randint(3, 8)
        near = d - radius
        t = s.sqrt(d * d - radius * radius)
        tx = radius * radius / d
        ty = radius * t / d
        area = s.simplify(radius * t ** 3 / d ** 2)
        angle = s.acos((tx - d) ** 2 / (t * t) - ty ** 2 / (t * t)) * 180 / s.pi
        inradius = s.simplify(area / (t + ty))
        ratio = s.simplify(inradius / radius)
        _checked(tx * tx + ty * ty, radius * radius)
        _checked((tx - d) * tx + ty * ty, 0)
        _checked(angle, 2 * s.asin(radius / d) * 180 / s.pi)
        given = f'From an external point P, PT and PU are tangents to a circle with centre O. The secant PO meets the nearer point A on the circle. $PA={near}$ and $PT=\\sqrt{{{d * d - radius * radius}}}$. T and U are the two points of contact.'
        tasks = ['Derive OP and the circle radius using the tangent-secant relationship.', 'Find the angle TPU and the area of triangle PTU.', 'Allow a different circle and external point with the same tangent length PT and the same tangent-triangle area. Derive all possible positive circle radii and prove completeness, then give the ratio of the larger radius to the smaller radius.'] if insane else ['Determine OP and the radius of the circle.', 'Find the angle between the two tangents.', 'Find the area of triangle PTU.']
        other_radius = s.simplify(t * t / radius)
        radii = sorted([radius, other_radius], key=float)
        _checked(other_radius * t ** 3 / (other_radius ** 2 + t * t), area)
        inverse_ratio = s.simplify(radii[1] / radii[0])
        answers = [s.Tuple(d, radius), s.Tuple(angle, area) if insane else angle, s.Tuple(*radii, inverse_ratio) if insane else area]
        scale = 100 / float(radius)
        P = (420, 175)
        O = (185, 175)
        X = lambda q: 185 + float(q) * scale
        Y = lambda q: 175 - float(q) * scale
        shrink = min(1, 220 / (float(d) * scale))
        scale *= shrink
        P = (X(d), 175)
        body = f'<circle cx="185" cy="175" r="{float(radius) * scale}" fill="none" stroke="currentColor" stroke-width="2.5"/>' + _line(*P, X(tx), Y(ty)) + _line(*P, X(tx), Y(-ty)) + _line(185, 175, *P) + _line(X(tx), Y(ty), X(tx), Y(-ty))
        for point, label in [((185, 175), 'O'), (P, 'P'), ((X(tx), Y(ty)), 'T'), ((X(tx), Y(-ty)), 'U'), ((X(radius), 175), 'A')]:
            body += _text(point[0] + 8, point[1] - 10, label)
        working = f'Power of P: PT²=PA(PA+2r), so r={radius} and OP={d}. Tangent points are ({tx},±{ty}) relative to O. Orthogonality is verified. Angle TPU={angle} degrees; area PTU={area}. Semiperimeter={t + ty}, giving inradius={inradius} and ratio={ratio}. For a fixed tangent length t and area K, K r²-t³ r+K t²=0. Its two positive roots are {radii[0]} and {radii[1]}, giving larger/smaller ratio {inverse_ratio}; no other radii satisfy this quadratic.'
        if insane:
            working = (f'For the reference circle, power of P gives $PT^2=PA(PA+2r_0)$, so $r_0={radius}$ and $OP={d}$. '
                f'Write $t=PT={s.latex(t)}$. In a general configuration of radius $r$ with this fixed tangent length, $OP=\\sqrt{{r^2+t^2}}$. '
                'Taking O as the origin and OP as the horizontal axis, tangency gives '
                '$T=(r^2/OP,rt/OP)$ and $U=(r^2/OP,-rt/OP)$. Hence the base TU is $2rt/OP$ '
                'and its distance from P is $t^2/OP$, so the triangle area is $K=rt^3/(r^2+t^2)$. '
                f'The reference configuration has $K={s.latex(area)}$. Fixing t and K gives $Kr^2-t^3r+Kt^2=0$. '
                f'The positive roots are ${s.latex(radii[0])}$ and ${s.latex(radii[1])}$. '
                f'Both give the same t and K by substitution; PA changes in the second configuration. '
                f'A quadratic has no further roots, and the requested larger/smaller radius ratio is ${s.latex(inverse_ratio)}$.')

    else:
        l, w, h = (rng.randint(3, 7), rng.randint(3, 6), rng.randint(4, 8))
        scale = rng.randint(2, 4)
        volume = l * w * h * scale ** 3
        diag = s.sqrt(l * l + w * w + h * h) * scale
        angle = s.atan(s.Rational(h, 1) / s.sqrt(l * l + w * w)) * 180 / s.pi
        nets = [s.sqrt((l + w) ** 2 + h * h), s.sqrt((l + h) ** 2 + w * w), s.sqrt((w + h) ** 2 + l * l)]
        shortest = min(nets, key=float) * scale
        given = f'A cuboid ABCDEFGH has base ABCD, with E,F,G,H vertically above A,B,C,D. Its mutually perpendicular edge lengths AB, BC, AE are in ratio {l}:{w}:{h}, and its volume is {volume} cubic units.'
        tasks = ['Determine all three dimensions and space diagonal AG.', 'Find the angle between AG and plane ABCD.', 'By comparing every two-face unfolding, determine the shortest surface path from A to G and justify the global minimum.'] if insane else ['Determine the three dimensions from the volume and ratio.', 'Find the angle between AG and plane ABCD.', 'Compare the possible two-face unfoldings and find the shortest surface path from A to G.']
        if insane:
            circum = diag / 2
            tasks[-1] = 'Find the shortest surface path from A to G by checking all unfoldings. Then find the ratio of the circumcircle area of right triangle ABG to the square of that shortest path.'
            target = s.pi * circum ** 2 / shortest ** 2
        else:
            target = shortest
        answers = [s.Tuple(l * scale, w * scale, h * scale, diag), angle, s.Tuple(shortest, target) if insane else target]
        from math_figures import _cuboid
        body = _cuboid(random.Random(seed), 'hard')[4]
        import re
        body = re.sub('<text[^>]*>[^<]* cm</text>', '', body)
        working = f'Let lengths be {l}t,{w}t,{h}t. The volume gives t={scale}; AG={diag}. Base diagonal gives tan(angle)={h}/sqrt({l * l + w * w}); angle={angle}. The three unfolding lengths are ' + ', '.join((str(n * scale) for n in nets)) + f'; the minimum is {shortest}. Triangle ABG is right-angled at B, so its circumradius is AG/2 and circumcircle area is {s.pi * (diag / 2) ** 2}.'
    return _finish(family, 'Extended ' + {'line': 'coordinate geometry', 'quadratic': 'quadratic geometry', 'triangle': 'angle-bisector geometry', 'circle': 'circle geometry', 'cuboid': 'solid geometry'}[family], given, tasks, answers, working, body, kind, rng, difficulty=difficulty)
