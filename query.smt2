; Freehold SMT-LIB query
(set-logic ALL)
(declare-const p Int)
(assert (and (>= p 0) (<= p 100)))
(assert (not (and (>= p 50) (<= p 100))))
(check-sat)
