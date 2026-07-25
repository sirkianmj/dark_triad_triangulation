# DT3 Project Data Dictionary

## Core Trait Scales (Dark Triad Dirty Dozen - DTDD)
* `DTDD_1m` - `DTDD_4m`: Machiavellianism items (1-4)
* `DTDD_1p` - `DTDD_4p`: Psychopathy items (1-4)
* `DTDD_1n` - `DTDD_4n`: Narcissism items (1-4)
* `DTDD_1i`: Extended Impulsivity item
* `DTDD_1g`: Extended Short-term manipulation item
* `DTDD_1ma`: Extended Antisocial behavior item

## Composite Scores
* `score_Machiavellianism`: Sum of 4 Machiavellianism items (Range: 0-28)
* `score_Psychopathy`: Sum of 4 Psychopathy items (Range: 0-28)
* `score_Narcissism`: Sum of 4 Narcissism items (Range: 0-28)
* `score_DarkCore_Total`: Sum of all 12 DTDD items (Range: 0-84)

## External Correlates (Item-Level & Scales)
* `BFI_N_1` - `BFI_N_8`: Big Five Neuroticism items
* `BFI_A_1` - `BFI_A_9`: Big Five Agreeableness items
* `BFI_C_1` - `BFI_C_9`: Big Five Conscientiousness items
* `BFI_O_1` - `BFI_O_10`: Big Five Openness items
* `RSES_1` - `RSES_10`: Rosenberg Self-Esteem Scale items
* `TEQ_1` - `TEQ_16`: Toronto Empathy Questionnaire items
* `health_behaviour_1` - `health_behaviour_5`: Health-risk behaviors (smoking, alcohol, drugs)

## Demographics & Metadata
* `age`: Age in years (Filtered >= 18)
* `gender`: Respondent gender (Male/Female/Other)
* `education`: Highest education level
* `sample_origin`: Origin sample (`sample_1_community`, `sample_2_student`, `sample_3_representative`)
