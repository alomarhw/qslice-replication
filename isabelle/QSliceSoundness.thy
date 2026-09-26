(* QSliceSoundness.thy

   Soundness of causal-cone backward slicing for circuits of local operations, relative to a
   reduced-state semantics.

   Replaces the submitted SemanticPreservation_v2.thy, which proved its obligations from global axioms
   that were unsound as stated. Here nothing is axiomatized globally. The two semantic facts used are
   assumptions of the locale `local_semantics`, and both hold for quantum circuits with density-matrix
   semantics, where rdm W is the partial trace onto W and every operation is a CPTP map acting on its
   support. That includes unitaries, non-selective measurement and reset, and a measurement together
   with the gate it classically controls, taken as one operation on the union of their qubits.
     locality:   an operation acting outside W does not change the reduced state on W
                 (no-signalling);
     dependence: the reduced state on W after an operation depends only on the reduced state on
                 W together with the operation's support.
   The quantum instance is standard linear algebra and is NOT mechanized here. To show the assumptions
   are satisfiable, so that the theorems are not vacuous, the locale is interpreted in a classical
   model at the end of this file.

   Scope of the guarantee. The theorem covers the causal-cone slice `cone`: keep an operation iff its
   support meets the qubits the rest of the slice still needs. QSlice's separability pruning removes
   further operations only after an exact runtime check of the criterion's reduced state, so it is not
   covered by this proof. The proof justifies the sound starting point of the slicer; the runtime check
   justifies each prune.
*)

theory QSliceSoundness
  imports Main "HOL-Library.Sublist"
begin

locale local_semantics =
  fixes apply_op :: "'op \<Rightarrow> 's \<Rightarrow> 's"
    and supp     :: "'op \<Rightarrow> nat set"
    and rdm      :: "nat set \<Rightarrow> 's \<Rightarrow> 'r"
  assumes locality:
    "supp g \<inter> W = {} \<Longrightarrow> rdm W (apply_op g \<rho>) = rdm W \<rho>"
  and dependence:
    "rdm (W \<union> supp g) \<rho> = rdm (W \<union> supp g) \<sigma> \<Longrightarrow>
     rdm W (apply_op g \<rho>) = rdm W (apply_op g \<sigma>)"
begin

text \<open>A circuit is a list of operations, applied left to right.\<close>
fun run :: "'op list \<Rightarrow> 's \<Rightarrow> 's" where
  "run [] \<rho> = \<rho>"
| "run (g # gs) \<rho> = run gs (apply_op g \<rho>)"

text \<open>need P W: the qubits whose state before P can influence the reduced state on W after P.\<close>
fun need :: "'op list \<Rightarrow> nat set \<Rightarrow> nat set" where
  "need [] W = W"
| "need (g # gs) W = (if supp g \<inter> need gs W = {} then need gs W else need gs W \<union> supp g)"

text \<open>cone P W: the causal-cone backward slice of P for criterion W.\<close>
fun cone :: "'op list \<Rightarrow> nat set \<Rightarrow> 'op list" where
  "cone [] W = []"
| "cone (g # gs) W = (if supp g \<inter> need gs W = {} then cone gs W else g # cone gs W)"

lemma cone_subseq: "subseq (cone P W) P"
  by (induction P) auto

lemma criterion_needed: "W \<subseteq> need P W"
  by (induction P) auto

text \<open>Generalised soundness: states that agree on the needed qubits give the same reduced state on W,
  one run through the full circuit and the other through the slice.\<close>
lemma cone_sound_gen:
  "rdm (need P W) \<rho> = rdm (need P W) \<sigma> \<Longrightarrow> rdm W (run P \<rho>) = rdm W (run (cone P W) \<sigma>)"
proof (induction P arbitrary: \<rho> \<sigma>)
  case Nil
  then show ?case by simp
next
  case (Cons g gs)
  show ?case
  proof (cases "supp g \<inter> need gs W = {}")
    case True
    have "rdm (need gs W) (apply_op g \<rho>) = rdm (need gs W) \<rho>"
      using locality[OF True] .
    also have "\<dots> = rdm (need gs W) \<sigma>"
      using Cons.prems True by simp
    finally have "rdm W (run gs (apply_op g \<rho>)) = rdm W (run (cone gs W) \<sigma>)"
      by (rule Cons.IH)
    with True show ?thesis by simp
  next
    case False
    have "rdm (need gs W \<union> supp g) \<rho> = rdm (need gs W \<union> supp g) \<sigma>"
      using Cons.prems False by simp
    then have "rdm (need gs W) (apply_op g \<rho>) = rdm (need gs W) (apply_op g \<sigma>)"
      by (rule dependence)
    then have "rdm W (run gs (apply_op g \<rho>)) = rdm W (run (cone gs W) (apply_op g \<sigma>))"
      by (rule Cons.IH)
    with False show ?thesis by simp
  qed
qed

text \<open>Main theorem: the causal-cone slice preserves the reduced state of the criterion qubits.\<close>
theorem cone_sound: "rdm W (run P \<rho>) = rdm W (run (cone P W) \<rho>)"
  by (rule cone_sound_gen) (rule refl)

end

section \<open>Non-vacuity: a classical model of the locale\<close>

text \<open>States assign a bit to every wire. An operation is a support Q and a function that may read and
  write only the wires in Q. The reduced state on W is the restriction of the state to W.\<close>

type_synonym cstate = "nat \<Rightarrow> bool"
type_synonym cop = "nat set \<times> (cstate \<Rightarrow> cstate)"

definition c_restrict :: "nat set \<Rightarrow> cstate \<Rightarrow> cstate" where
  "c_restrict Q \<rho> = (\<lambda>x. if x \<in> Q then \<rho> x else False)"

definition c_apply :: "cop \<Rightarrow> cstate \<Rightarrow> cstate" where
  "c_apply g \<rho> = (\<lambda>q. if q \<in> fst g then snd g (c_restrict (fst g) \<rho>) q else \<rho> q)"

definition c_rdm :: "nat set \<Rightarrow> cstate \<Rightarrow> (nat \<Rightarrow> bool option)" where
  "c_rdm W \<rho> = (\<lambda>q. if q \<in> W then Some (\<rho> q) else None)"

interpretation classical: local_semantics c_apply fst c_rdm
proof
  fix g :: cop and W :: "nat set" and \<rho> :: cstate
  assume "fst g \<inter> W = {}"
  then show "c_rdm W (c_apply g \<rho>) = c_rdm W \<rho>"
    by (auto simp: c_rdm_def c_apply_def fun_eq_iff)
next
  fix W :: "nat set" and g :: cop and \<rho> \<sigma> :: cstate
  assume h: "c_rdm (W \<union> fst g) \<rho> = c_rdm (W \<union> fst g) \<sigma>"
  have agree: "\<rho> q = \<sigma> q" if "q \<in> W \<union> fst g" for q
    using fun_cong[OF h, of q] that by (simp add: c_rdm_def)
  have r: "c_restrict (fst g) \<rho> = c_restrict (fst g) \<sigma>"
    using agree by (auto simp: c_restrict_def fun_eq_iff)
  show "c_rdm W (c_apply g \<rho>) = c_rdm W (c_apply g \<sigma>)"
  proof (rule ext)
    fix q
    show "c_rdm W (c_apply g \<rho>) q = c_rdm W (c_apply g \<sigma>) q"
      using agree[of q] by (simp add: c_rdm_def c_apply_def r)
  qed
qed

text \<open>A concrete instance of the main theorem in the model: a circuit whose second operation acts
  only on wire 2 is sliced away for criterion {0}.\<close>
lemma classical_example:
  "classical.cone [({0,1}, id), ({2}, id)] {0} = [({0,1}, id)]"
  by simp

end
