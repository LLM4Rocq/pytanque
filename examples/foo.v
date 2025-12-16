From Coq Require Import Lia.
From Coq Require Import ssreflect ssrbool.
Theorem t:
    forall n: nat, 1 + n > n.
Proof.
  intro n.
  lia.
Qed.

Lemma addnC n m : n + m = m + n.
Proof. by elim: n => //= ? ->. Qed.

Lemma addnAC n m l : n + m + l = m + (n + l).
Proof.
  by elim : n => //= ? ->.
Qed.

Notation "x ⊕ y" := (x + y) (at level 50, left associativity).

Lemma use_notation_wo_scope : 1 ⊕ 2 = 3.
Proof.
  reflexivity.
Qed.

Declare Scope my_scope.
Notation "x ⊕_s y" := (x + y) (at level 50, left associativity): my_scope.
Open Scope my_scope.

Lemma use_notation_w_scope : 1 ⊕_s 2 = 3.
Proof.
  reflexivity.
Qed.