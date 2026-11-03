"""Constructed proof tasks: public premises, symbolic checks and complete argument keys."""
import random, re
import sympy as s
from answer_parts import SolvedPart

def construct(family, difficulty, seed):
    from advanced_math_figures import geometry, integration
    from tools import QuestionDraft
    base = (integration if family.endswith('_integral') else geometry)(family, 'insane' if difficulty == 'insane' else 'hard', 'long_answer', seed)
    x, m, u, v = s.symbols('x m u v', real=True)
    rng = random.Random(seed)
    checks = []
    if family == 'quadratic':
        a, h, k = (rng.randint(1, 3), rng.randint(1, 3), -rng.randint(1, 5))
        q = k - m * h - m * m / (4 * a)
        assert s.simplify(a * (x - h) ** 2 + k - (m * x + q) - a * (x - h - m / (2 * a)) ** 2) == 0
        givens = f'Let $f(x)={a}(x-{h})^2+({k})$ and let $\\ell(x)=mx+q$, where m and q are real. A tangent has exactly one point of contact. P=(u,v) is a point in the plane.'
        tasks = [f'Derive the necessary and sufficient condition $q={k}-{h}m-m^2/{4 * a}$ for tangency, and determine the point of contact.', f'Prove that every such tangent satisfies $f(x)\\ge\\ell(x)$ for all real x, with equality at exactly one x.', 'Classify the number of distinct real tangents through P, proving every case and treating a repeated root explicitly.']
        if difficulty == 'insane':
            tasks[-1] += ' Then derive the complete locus of P for which two tangents through P are perpendicular, and prove that two distinct real tangents actually exist everywhere on that locus.'
        explanations = [f'Completing the square in f(x)-mx-q gives {a}(x-{h}-m/{2 * a})²+{k}-{h}m-q-m²/{4 * a}. Exactly one root requires the constant term to vanish. Contact x={h}+m/{2 * a}, y={k}+m²/{4 * a}.', f'The preceding difference is {a}(x-{h}-m/{2 * a})². Its leading coefficient is positive, so it is nonnegative and vanishes only at the contact x.', f'The condition v=mu+q gives m²-{4 * a}(u-{h})m+{4 * a}(v-({k}))=0. Its discriminant is {16 * a}({a}(u-{h})²+{k}-v): two tangents below the parabola, one on it, none above it. Their slope product is {4 * a}(v-({k})). Perpendicularity is equivalent to this product=-1, hence v={k}-1/{4 * a}. On this line the discriminant is {16 * a}({a}(u-{h})²+1/{4 * a})>0; thus both real slopes exist and are distinct.']
        checks = [{'kind': 'equivalence', 'left': f'{a}*(x-{h})**2+({k})-(m*x+({k}-{h}*m-m**2/{4 * a}))', 'right': f'{a}*(x-{h}-m/{2 * a})**2', 'variables': ['x', 'm'], 'purpose': 'The completed square comes from subtracting the public line from the public parabola.'}]
    elif family == 'circle':
        givens = 'A circle has centre O=(0,0) and radius r>0. P=(d,0), with d>r, has tangents PT and PU, with T above OP and U below it. Let t=PT and K be the area of triangle PTU. A is the nearer intersection of OP with the circle.'
        tasks = ['Using the circle equation and perpendicular radius/tangent relationship, derive the coordinates of T and U and the tangent length t.', 'Derive the area formula $K=rt^3/(r^2+t^2)$.', 'For a fixed t>0, prove the largest possible K and characterize every equality case.']
        if difficulty == 'insane':
            tasks[-1] += ' For each prescribed K>0, classify the number of possible positive radii; prove completeness and derive the product of the radii when two exist.'
        explanations = ['Write T=(X,Y). OT perpendicular PT gives X(X-d)+Y²=0; the circle gives X²+Y²=r². Therefore X=r²/d, Y=r sqrt(d²-r²)/d>0. U has the negative Y; t²=d²-r²>0.', 'TU=2rt/d and the perpendicular distance from P to TU is d-r²/d=t²/d. Half base times height gives K=rt³/d²=rt³/(r²+t²).', 'Since (r-t)²>=0, r²+t²>=2rt, hence K<=t²/2, with equality exactly r=t and d=sqrt(2)t. A prescribed K gives Kr²-t³r+Kt²=0. The discriminant t²(t⁴-4K²) is positive for 0<K<t²/2 (two positive roots: positive sum t³/K and product t²), zero at K=t²/2 (one positive radius), and negative above the maximum (none). No roots are lost because K>0 and r²+t²>0; each positive root gives d=sqrt(r²+t²)>r and a valid exterior point.']
        r, t = s.symbols('r t', positive=True)
        assert s.simplify(t ** 2 / 2 - r * t ** 3 / (r * r + t * t) - t * t * (r - t) ** 2 / (2 * (r * r + t * t))) == 0
        checks = [{'kind': 'equivalence', 'left': 't**2/2-r*t**3/(r**2+t**2)', 'right': 't**2*(r-t)**2/(2*(r**2+t**2))', 'variables': ['r', 't'], 'purpose': 'The public area bound reduces to a nonnegative square for positive r,t.'}]
    elif family == 'triangle':
        givens = 'In triangle ABC, AB=c>0, AC=b>0 and angle BAC is 60 degrees. AD is the internal angle bisector, meeting BC at D.'
        tasks = ['Use the angle-bisector relationship to derive the coordinates of D after placing A at the origin and AB on the positive x-axis.', 'Derive $AD=\\sqrt{3}bc/(b+c)$, justifying the positive square root.', 'With b+c=p fixed and positive, prove the sharp upper bound on AD and characterize equality.']
        if difficulty == 'insane':
            tasks[-1] += ' For a prescribed value L>0 of AD, classify the number of ordered positive pairs (b,c) with b+c=p, including the limiting and equality cases.'
        explanations = ['B=(c,0), C=(b/2,sqrt(3)b/2). BD/DC=AB/AC=c/b, so D=(bB+cC)/(b+c)=(3bc/(2(b+c)),sqrt(3)bc/(2(b+c))).', 'Squared distance AD² is 3b²c²/(b+c)². Lengths and b+c are positive, so AD=sqrt(3)bc/(b+c).', 'From (b-c)²>=0, bc<=(b+c)²/4=p²/4, so AD<=sqrt(3)p/4, attained exactly b=c=p/2. A prescribed L yields b²-pb+Lp/sqrt(3)=0 and c=p-b. For 0<L<sqrt(3)p/4 there are two distinct ordered positive pairs; at the bound one; above it none. L=0 is not attained by positive sides, although it is approached as one side tends to zero.']
        b, c = s.symbols('b c', positive=True)
        assert s.simplify((3 * b * c / (2 * (b + c))) ** 2 + (s.sqrt(3) * b * c / (2 * (b + c))) ** 2 - 3 * b * b * c * c / (b + c) ** 2) == 0
        svg = base.figure['svg']
        svg = re.sub('(<text x="180" y="330"[^>]*>)[^<]*', '\\1c', svg)
        svg = re.sub('(<text x="100" y="180"[^>]*>)[^<]*', '\\1b', svg)
        base.figure['svg'] = svg
        checks = [{'kind': 'equivalence', 'left': '(3*b*c/(2*(b+c)))**2+3*(b*c/(2*(b+c)))**2', 'right': '3*b**2*c**2/(b+c)**2', 'variables': ['b', 'c'], 'purpose': 'Squared distance to the derived point D verifies the bisector-length formula.'}]
    elif family == 'line':
        givens = 'For real u,v and t>0, let L1: 2x+3y=ut and L2: 3x-2y=vt. Their x-intercepts are P and Q and their intersection is R.'
        tasks = ['Derive P, Q and R as functions of t and prove that L1 and L2 are perpendicular.', 'Derive the area formula $[PQR]=(3u-2v)^2t^2/156$, using absolute values correctly.', 'For a prescribed positive area A, prove when there is exactly one positive t and when there is no solution.']
        if difficulty == 'insane':
            tasks[-1] += ' Classify the degenerate case completely, including prescribed area zero, and prove how every distance and the circumradius scale with t in the nondegenerate case.'
        explanations = ['P=(ut/2,0), Q=(vt/3,0), R=((2u+3v)t/13,(3u-2v)t/13). The normals (2,3) and (3,-2) have dot product 0; thus the lines are perpendicular.', 'Base PQ=|3u-2v|t/6 and height=|3u-2v|t/13. Their product divided by 2 is (3u-2v)²t²/156.', 'If 3u!=2v, the coefficient C=(3u-2v)²/156 is positive. A>0 has unique positive t=sqrt(A/C); A=0 has none under t>0. If 3u=2v, all three points coincide for every positive t, so no positive-area solution exists and every positive t gives area zero. Coordinates scale by t, hence distances and circumradius scale by t; area scales by t². The right angle at R puts R on the circle with diameter PQ, so circumradius=PQ/2 in the nondegenerate case.']
    elif family == 'cuboid':
        givens = 'A cuboid ABCDEFGH has mutually perpendicular positive edge lengths a,b,c, base ABCD, and E,F,G,H vertically above A,B,C,D. Let d denote its space-diagonal length. Let S be the shortest surface distance from A to G among paths confined to two adjacent faces.'
        tasks = ['Derive $d^2=a^2+b^2+c^2$ using orthogonal projections.', 'Derive the three possible two-face unfolding lengths and justify why the shortest admissible route is their minimum.', 'Prove which pair of edges must be combined in the minimizing unfolding, including all tie cases.']
        if difficulty == 'insane':
            tasks[-1] += ' For fixed d, prove the sharp maximum S and its equality case, then determine whether the lower bound d is attained for positive edge lengths.'
        explanations = ['Applying Pythagoras first to the base diagonal, then to its perpendicular height, gives d²=a²+b²+c².', 'A shortest path can be straightened across an edge into the adjacent face. Removing unnecessary crossings and using the symmetry of opposite vertices yields the three admissible rectangle unfoldings, with squared lengths (a+b)²+c², (a+c)²+b², (b+c)²+a². Thus S²=d²+2min(ab,ac,bc).', 'Order a<=b<=c. Then ab<=ac and ab<=bc, so combining the two smallest edges minimizes the unfolding; equal products give exactly the ties (equal positive relevant edges). Since min(ab,ac,bc)<= (ab+ac+bc)/3 <=d²/3, S²<=5d²/3. Equality requires a=b=c, giving S=d sqrt(5/3). For all positive edges min pair product>0, so S>d. Taking a=b=epsilon and c=sqrt(d²-2epsilon²) makes S tend to d, so the lower bound is an unattained infimum.']
    else:
        givens = base.question.split(' The diagram is schematic')[0]
        tasks = re.findall('\\([abc]\\) (.*?)(?=\\n\\n\\([abc]\\)|$)', base.question, re.S)
        tasks = ['Derive from the stated region and density, with all coordinate bounds, domains and Jacobians justified: ' + task for task in tasks]
        from answer_parts import numeric_answer
        explanations = [numeric_answer(part) for part in base.answer_parts]
        checks = []
    if len(tasks) > 2:
        tasks[1] = tasks[1] + '\n\nAdditional requirement: ' + tasks[2]
        explanations[1] = explanations[1] + '\n\n' + explanations[2]
    if difficulty == 'easy':
        tasks = tasks[:1]
        explanations = explanations[:1]
    else:
        tasks = tasks[:2]
        explanations = explanations[:2]
    question = givens + ' The figure is schematic, not a source of additional assumptions. Give a complete proof or derivation for each part; numerical agreement or measurement from the figure alone is insufficient.\n\n' + '\n\n'.join((f"({'abc'[i]}) {task}" for i, task in enumerate(tasks)))
    parts = [SolvedPart(label='abc'[i], kind='symbolic', answer=text, requirements=tasks[i], checks=checks if i == 0 else []) for i, text in enumerate(explanations)]
    base.figure['alt'] = givens[:1400]
    import html
    svg = re.sub('<desc>.*?</desc>', lambda _: '<desc>' + html.escape(givens[:1400]) + '</desc>', base.figure['svg'], flags=re.S)
    if family == 'quadratic':
        from math_figures import _graph, _svg
        from math_figures import _line, _path, _text
        xmin, xmax = (h - 3, h + 3)
        ymin, ymax = (k - 1, 9 * a + k + 1)
        X = lambda xx: 70 + 370 * (xx - xmin) / (xmax - xmin)
        Y = lambda yy: 305 - 265 * (yy - ymin) / (ymax - ymin)
        points = [(X(xmin + (xmax - xmin) * i / 120), Y(a * (xmin + (xmax - xmin) * i / 120 - h) ** 2 + k)) for i in range(121)]
        svg = _svg(_line(50, Y(0), 470, Y(0)) + _line(X(0), 320, X(0), 30) + _path(points) + _text(480, Y(0), 'x') + _text(X(0) + 15, 25, 'y'), 'Tangent geometry', givens)
    base.figure['svg'] = svg
    return QuestionDraft(question=question, question_type='proof', canonical_answer='\n'.join((f"({'abc'[i]}) {text}" for i, text in enumerate(explanations))), solution='\n\n'.join((f"({'abc'[i]}) {text}" for i, text in enumerate(explanations))), answer_parts=parts, figure=base.figure, formula_focus=base.formula_focus)
