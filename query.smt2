; Freehold SMT-LIB query
(set-logic ALL)
(declare-const x Int)
(assert (> x 0))
(assert (not (> (+ x 1) 1)))
(check-sat)
