Include: <../base-walls-min.g>

wall1 (world){ shape:ssBox, Q:"t(-0.679 1.223 0.3)", size:[0.1 1.5 0.6 .02], color:[0.69 0.51 0.45], contact: 1 }

wall2 (world){ shape:ssBox, Q:"t(-0.679 -1.205 0.3)", size:[0.1 1.5 0.6 .02], color:[0.69 0.51 0.45], contact: 1 }

obs1Joint(world){ Q:[0.0 0.0 0.1] }
obs1(obs1Joint) { shape:ssBox, Q:"t(-0.318 0.006 .0)", size:[0.3 1.2 .2 .02], logical:{ movable_o }, color:[1.0 1.0 1.0], joint:rigid, contact: 1 }

egoJoint(world){ Q:[0 0 0.1] }
ego(egoJoint) {
    shape:ssCylinder, Q:[1.425 0.532 0], size:[0.2 0.2 .02], color:[0.96 0.74 0.30], logical:{agent}, limits: [-4 4 -4 4],
    joint:transXY, contact: 1
}

obj1Joint(world){ Q:[0.0 0.0 0.1] }
obj1(obj1Joint) { shape:ssBox, Q:"t(0.741 1.309 .0)", size:[0.3 0.3 .2 .02], logical:{ movable_go }, color:[0.549 0.6118 0.3608], joint:rigid, contact: 1 }

goal1 (floor){ shape:ssBox, Q:"t(-1.335 -1.572 .1)", size:[0.3 0.3 .2 .02], color:[0.549 0.6118 0.3608 .3], contact:0, joint:rigid, logical:{goal} }

