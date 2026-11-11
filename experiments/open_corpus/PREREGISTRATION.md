# Analysis plan: source attribution on the open-access corpus

Written on 2026-11-09, before any answer to the final question bank was generated. The commit that adds this file fixes the code and the plan. A second commit on the same day, also before any such answer, added the cost outcome, the claim-level judge and the human rating.

## Frozen inputs

| Input | Value |
|---|---|
| Corpus | corpus.txt, 112 English documents, SHA-256 fd56b8230d2213cd99b18204e5c3f485dbed00b3cdeb74fa560a6be85ee7c5de |
| Question bank | questions.json, 418 answerable and 185 near-miss questions, SHA-256 1cd45ba0f70c88ff22c3272ef264728ccb67478ab6862c9c20ec678c461b716c |
| Answer model | gpt-4o-mini-2024-07-18, temperature 0 |
| Retrieval | text-embedding-3-small, top 6, chunks of 1100 characters with overlap 200 |
| Languages | English; Spanish, Portuguese, Turkish and Polish as translated queries over the English corpus |

## Unit of analysis and primary outcome

The unit is one answerable English question, using its first complete run (repeat 0). The primary outcome is gold-source F1 over the distinct sources an answer cites: 0 if the gold source is not cited, otherwise 2p/(p+1), where p is 1 divided by the number of distinct cited sources.

An answer with no citation, an unparseable reply, or an abstention scores 0. Citation of a source that was not retrieved counts as a wrong source. No question is excluded after this point.

## Primary comparisons

Twelve paired comparisons of F1, each two-sided, corrected together with the Holm procedure at alpha 0.05:

1. document vs none
2. labels_only vs document
3. chunk vs document
4. chunk vs labels_only
5. chunk vs top_chunk
6. to 12. each of clean_prompt, numbered, json_claims, quote_first, posthoc_similarity, posthoc_llm and ablation vs chunk

Each comparison reports the mean paired difference, a sign-flip permutation test on question-level differences (10,000 permutations, seed 20261109), and a 95% bootstrap interval resampling gold documents (10,000 samples, same seed), because questions from one document are not independent.

A non-significant comparison is reported as inconclusive, not as equivalence. No method is declared best unless it differs significantly from the reference.

## Secondary outcomes (descriptive, no correction)

- Recall and precision of the gold source; exact McNemar test on recall for the twelve comparisons.
- Mean distinct sources cited, answers without citation, citations outside the retrieved sources, invalid references, unparseable replies, and verified quotes.
- Near-miss questions: share of answers with no citation and share judged as abstaining.
- False abstention on answerable questions.
- Cost: input tokens, output tokens, calls and USD per answer for each method, and the total cost of the study by stage, including pilots and failed runs.
- Stability: 50 randomly chosen answerable English questions, 5 runs each (seed 20261109): modal citation agreement, identical citations, identical text, and standard deviation of F1.

## Languages

After the English run, three methods are run in the four other languages: chunk, and the two methods with the highest English F1 among clean_prompt, numbered, json_claims, quote_first, posthoc_similarity, posthoc_llm and ablation. Ties are broken by higher precision. If fewer than two differ from each other, the order in this list decides.

For each language and method the analysis reports F1 and its paired difference from English, with the same interval method. These analyses are descriptive. The selection depends on English results, so English performance of the selected methods is not an unbiased estimate.

## Claim-level support (secondary)

F1 shows whether the right document was named, not whether it supports what the answer says. This is measured on the five analysed methods: document, labels_only, chunk, and the two methods selected for the other languages. For these methods, a language-model judge (gpt-4.1-mini-2025-04-14) assesses each claim against the passages of the cited source among those retrieved, on 100 randomly chosen answerable English questions (seed 20261109), for each model run. The two selected methods are ablation and clean_prompt, chosen by the rule above from the English run.

An answer's support is the share of its claims the judge finds supported. An answer is fully supported if that share is at least 0.8. Answers that abstain, have no citation, or have no claims score 0. A control tests claims from another question against each passage set, using the chunk method, to measure judge leniency.

Exploratory, added after the English F1 results were seen: top_chunk is scored on the answer written without labels (the one used by ablation), to test whether naming the first retrieved source is also enough at claim level. Its result does not enter any corrected comparison.

## Human rating (after the automatic results)

Nurses from the project rate sentences after the automatic results exist, under these rules, which are fixed before those results are seen:

- 120 items: 21 sentences for each of the five analysed methods (105 in total), sampled with seed 20261109 from cited sentences in primary English answers, in equal numbers across the models run, plus 15 control pairs joining a sentence to a passage from an unrelated answer.
- Each item shows one sentence and the passages of its cited source. The rater answers whether the passages support the sentence. Raters do not see the method or the model, and items are shuffled.
- Each item is rated independently by two nurses who read clinical English. Agreement is reported as Cohen's kappa with a bootstrap 95% interval. Disagreements stay in the data as not agreed; they are not resolved afterwards.
- Reported outcomes are the share supported per method among agreed items with a 95% interval, the acceptance of control pairs, and the sensitivity and specificity of the language-model judge against agreed human ratings.
- If human ratings contradict the automatic results, both are reported. The rating does not assess clinical accuracy.

### Amendment to the human rating (2026-11-10)

Written after the automatic results were seen, and before any item was sampled or rated. It therefore replaces a rule that had been fixed before those results. The reason is that the judge marked only 427 of 8,013 checked claims (5.3%) as unsupported, so about 6 of the 105 sampled sentences would be negative and specificity would rest on the 15 unrelated controls, which are easy.

The total stays at 120 items, so the time asked of each nurse does not change. Items, with seed 20261109, in equal numbers across the models run:

- 75 random sentences, 15 per analysed method, drawn from the cited sentences in primary English answers that are not in the doubted pool.
- 30 doubted sentences, 6 per analysed method, drawn from the doubted pool: answers in the claim-judge sample with at least one claim marked unsupported by the first judge, taking from each the sentence with the highest word overlap with that claim.
- 8 near-topic pairs joining a sentence to the retrieved passages of a source the answer did not cite. Their label is decided by the raters and is not assumed to be negative.
- 7 control pairs joining a sentence to a passage from an unrelated answer, as before.

Everything else about the rating stays as above: the raters, what they see, shuffling, and no resolution of disagreements. Changes to the analysis:

- Both automated judges rate the same 120 items, as sentence and passages, because the judges otherwise score extracted claims and not sentences.
- Share supported per method, kappa, and the sensitivity and specificity of each judge are reported on the non-control items with weights equal to the inverse of each stratum's sampling fraction, since the doubted stratum was selected using the first judge. The unweighted values on the random stratum are also reported.
- Kappa is reported with raw agreement and the share rated supported, since kappa is low when one category dominates.
- Control acceptance is computed on the 7 control pairs only.

### Second amendment to the human rating (2026-11-10)

Written before any item was sampled or rated. It replaces the sample and outcomes of the first amendment. The time was underestimated: the cited passages of an item have about 650 words on average, so 120 items would require 5 to 6.5 hours of reading from each rater.

The purpose of the rating is now to validate the automated judges against human raters. There are 60 items, in two blocks of 30, with seed 20261109 and as evenly as possible across the models run:

- 35 random sentences, 7 per analysed method, from the cited sentences in primary English answers that are not in the doubted pool.
- 15 doubted sentences, 3 per analysed method, from the doubted pool defined in the first amendment.
- 5 near-topic pairs, joining a sentence to a retrieved passage of a source the answer did not cite. Their label is decided by the raters.
- 5 control pairs, joining a sentence to a passage from an unrelated answer.

Each item shows one sentence and one passage: for the random and doubted sentences, the cited passage with the highest word overlap with the sentence. The rater answers yes, partially, or no. Only yes counts as supported, in line with the "fully supported" question put to the judges. Two nurses who read clinical English rate every item independently, and disagreements stay in the data as not agreed.

Both automated judges rate the same 60 items, with the verification prompt, on the same sentence and passage. Reported outcomes: Cohen's kappa between raters with raw agreement and the share rated supported; acceptance of the control pairs; sensitivity and specificity of each judge against agreed human ratings, on the non-control items, weighted by the inverse of each stratum's sampling fraction, and the unweighted values on the random stratum. The share supported per method is no longer an outcome, since 7 items per method do not support it. A sentence supported only by another cited passage counts as unsupported for raters and judges alike, so the comparison between them remains valid. The rating does not assess clinical accuracy.

### Third amendment to the human rating (2026-11-10)

Written after the answers of the first rater were seen and before those of any other rater were received. More than two raters may take part. An item counts as agreed only when all raters give the same verdict, after reducing each answer to supported (yes) or not supported (partially or no). Other items stay in the data as not agreed. Agreement between raters is reported with Cohen's kappa if there are two raters and Fleiss' kappa if there are more. The automated judges have not been run on the 60 items at the time of writing.

## Query translation (added after the language results were seen)

Attribution was worse in Turkish and Polish, and the gold document reached the model less often. This second experiment tests one mitigation. It is reported as a separate study, designed after those results.

Each translated question is translated into English by the answer model for retrieval only. The model still receives the original question and answers it from the passages retrieved for the translation. The methods are chunk and top_chunk.

The primary outcome is the paired difference in F1 for chunk between this condition and the earlier language run, in each of the four languages, on the same questions. Each uses a sign-flip permutation test and a document bootstrap as above, corrected together with Holm at alpha 0.05. Secondary outcomes are the gold document at first rank and among the top 6, and F1 relative to English. The language run for comparison is run_20261109T120655Z.json.

## Replication with other models

Added on 2026-11-09, before any answer from these models was generated. Two further answer models are called through OpenRouter: anthropic/claude-haiku-5.5 (closed) and google/gemma-4-31b-it (open weights). Reasoning is disabled and temperature 0 is requested, although the provider may not apply it to every model. Retrieval, passages, prompts and the abstention judge are unchanged.

For each model: the full English run with all methods and the stability subset; chunk alone in the four other languages, because the retrieval step does not depend on the answer model; query translation with chunk and top_chunk, translated by that same model; and the claim-level judge on the same five methods and 100 questions. This replaces the language selection rule for these two models.

The twelve primary comparisons are repeated within each model, with Holm correction within that model, and reported as replications. The gpt-4o-mini results remain the primary analysis.

Checked on 2026-11-10, after the runs: OpenRouter lists no temperature parameter for anthropic/claude-haiku-5.5 on any endpoint, so its answers are taken as produced with the default sampling of the model. All endpoints of google/gemma-4-31b-it accept the parameter, but the endpoint serving each call was not recorded.

Deviation from the frozen parsing, made before these runs: Claude Haiku wraps JSON replies in a Markdown code block, so the parser now removes such a block. gpt-4o-mini replies were produced in JSON mode and are not affected.

Deviation during the replication runs: some google/gemma-4-31b-it calls did not finish, and two runs stalled in the structured-output methods. Calls through OpenRouter were therefore limited to 4,096 output tokens (the longest answer of any other method was about 3,600 characters). The limit applies to the final Gemma English run and to the Gemma language and query translation runs. The Claude Haiku runs and the gpt-4o-mini runs were made without it. In the final Gemma English run, 149 calls reached the limit (json_claims 19, quote_first 53, posthoc_llm 77). Replies that remained unparseable after the retries score 0 under the existing rule: 28 records (posthoc_llm 14, quote_first 12, json_claims 2).

Aborted runs, repeated under the run rules below: the Gemma English run was killed when the session that launched it closed, and its records were lost; the Claude Haiku language run was killed in the same way; and a first Claude Haiku English attempt failed. The next Gemma English run stalled. It was then resumed from its saved records to completion, which the run rules do not allow, and its operational counts and its final scores were seen. That run (run_20261109T161348Z) is excluded. The primary Gemma English run is run_20261109T170742Z, made from scratch afterwards with the same settings and sharing no records with it.

Limitation of the frozen parser, found after these runs and left unchanged: in a citation written as "(source: a; source: b)", the second label keeps its prefix and counts as a wrong source. It affects mainly Claude Haiku, in at most 13 of 418 answers per condition, and correcting it would change F1 by at most 0.005. gpt-4o-mini is affected in at most one answer per condition and Gemma in none.

Exploratory, added after the results were seen: on near-miss questions, abstentions that still cite a source are reported as a separate category, and those whose only text beyond the citation is the abstention sentence are counted as bare citations.

Exploratory, added after the results were seen: chunk F1 is broken down by the rank of the gold document in retrieval (first, ranks 2 to 6, not retrieved) in each language and model, and clean_prompt and ablation are compared with chunk in the four other languages for gpt-4o-mini, without correction. scripts/analyze_retrieval_rank.py produces both.

## Second automated judge (added 2026-11-10)

Added after the results of the first judge were seen and before any verdict of the second. It is a sensitivity analysis and does not replace the first judge. The judge is deepseek/deepseek-v4-flash through OpenRouter, an open-weight model from a provider that wrote no answer in the study, with temperature 0 requested, reasoning disabled, and DeepInfra as the only provider. It replaced mistralai/mistral-large-2512, whose run was stopped after 1,731 of 8,365 verdicts because of rate limits. Only counts of those verdicts were seen, never their agreement with the first judge, and they are not used. scripts/eval_second_judge.py runs it with the prompts of the first judge on:

- the claims already extracted by the first judge for the five analysed methods and top_chunk, in the three models, so that differences come from the verdict and not from the extraction, which remains an OpenAI step;
- the same control pairs;
- the near-miss answers of chunk and clean_prompt in the three models, for abstention.

Reported: Cohen's kappa with the first judge, with a 95% interval resampling gold documents, raw agreement, share of fully supported answers per method and model, control acceptance, and abstention counts. If the judges differ, both are reported and neither is preferred. Each verdict is an independent call, so a run interrupted by infrastructure resumes from its saved verdicts, unlike the answer runs, and any such resumption is reported.

## Automatic check of the translations (added 2026-11-10)

Added after the language results were seen and before any verdict of this check, because the translations were not reviewed by native speakers. It is a sensitivity analysis and does not replace such a review. scripts/eval_translation_check.py asks anthropic/claude-haiku-5.5 through OpenRouter, a model that did not translate the questions, with reasoning disabled, to compare each English question with each of its four translations (1,672 verdicts). The model has no temperature setting on OpenRouter. It replaced anthropic/claude-sonnet-5.5 before any verdict was obtained, because OpenRouter does not allow reasoning to be disabled for that model.

For each translation it returns same_meaning (yes, minor or no) and natural (yes, odd or no). A translation is flagged if same_meaning is no. Reported, for each language: the counts of each verdict; and, for chunk in each of the three answer models, the difference in F1 from English on all questions and without the flagged translations, and the share of questions with the gold document first among flagged and other translations. The conclusions on languages are qualified if the difference from English changes materially without the flagged translations. Each verdict is an independent call, so a run interrupted by infrastructure resumes from its saved verdicts.

## Run rules

- Prompts, methods, parsing and metrics do not change after this commit. Any necessary deviation is reported with its reason.
- The first complete run is primary. If a run aborts, its partial records are not inspected and the run is repeated, and this is reported.
- Other models, if run, follow this plan and are reported as replications.
- Citation correctness by a language-model judge is not part of this plan. Any later use is exploratory.

## Disclosed before this plan

- Earlier results on a fictional corpus (86 answerable questions) motivated this study.
- A 20-question smoke test on that earlier bank compared the methods. It is not used here.
- The final pipeline was tested on 26 questions from a pilot bank over 5 documents, excluding every question also in the final bank. Only operational counts were inspected: no citation, invalid references, parse errors and tokens. Gold-source scores were not inspected.

## Known limitations

- Questions and translations are model-generated. Translations were not reviewed by native speakers when this plan was frozen.
- The corpus is published literature used as test material. It was selected by title and metadata.
- Each question has a single gold source. Questions also answered by another retrieved passage were removed, using a language-model check on the per-chunk index.
- This evaluation measures attribution behaviour, not clinical accuracy or safety.
