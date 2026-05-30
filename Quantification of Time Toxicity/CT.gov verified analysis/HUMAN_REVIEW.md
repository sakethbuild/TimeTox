# Human Review — 52 Flagged Trials

Review the three sources and record your call in `human_review_worksheet.csv` (columns `human_decision` / `human_notes`). Reason groups below.

Legend: **pipe**=pipeline label · **CT.gov**=registrant type · **PubMed**=abstract extraction.

## 1. WRONG PMID (4 trials) — dataset PMID points to an unrelated paper; find correct PMID or exclude

### NCT01519700 (PMID 26122726)
- CT.gov: https://clinicaltrials.gov/study/NCT01519700  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/26122726
  - **Arm B (Radiosurgery + WBRT)** (TT=18.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`control`** ⬅FLAGGED
  - **Arm A (Radiosurgery alone)** (TT=6.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED

### NCT02101021 (PMID 30105668)
- CT.gov: https://clinicaltrials.gov/study/NCT02101021  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/30105668
  - **Arm A (VMP)** (TT=42.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`control`** ⬅FLAGGED
  - **Arm B (D-VMP)** (TT=42.0d): pipe=`intervention` · CT.gov=`control`(PLACEBO_COMPARATOR) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED

### NCT01539291 (PMID 30995176)
- CT.gov: https://clinicaltrials.gov/study/NCT01539291  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/30995176
  - **Arm B (Standard-dose GS-1101)** (TT=14.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`control`** ⬅FLAGGED
  - **Arm A (High-dose GS-1101)** (TT=14.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED

### NCT02883049 (PMID 32496902)
- CT.gov: https://clinicaltrials.gov/study/NCT02883049  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/32496902
  - **Very High Risk (VHR) B-ALL (Control Arm)** (TT=76.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`unresolved` → **final=`control`** ⬅FLAGGED
  - **Very High Risk (VHR) B-ALL - Control Arm** (TT=90.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`control`** ⬅FLAGGED
  - **High Risk (HR) B-ALL (Arm A/B)** (TT=76.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED
  - **Ph-like Dasatinib Arm** (TT=83.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED
  - **Down Syndrome (DS) HR B-ALL** (TT=83.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED
  - **Down Syndrome HR B-ALL Arm** (TT=84.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED

## 2. PUBMED UNRESOLVED — abstract doesn't establish the arm role (head-to-head, or arm not described); currently keeping pipeline label

### NCT00475085 (PMID 22915657)
- CT.gov: https://clinicaltrials.gov/study/NCT00475085  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/22915657
  - **Arm 3 (Aprepitant + Palonosetron + Dexamethasone)** (TT=1.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`unresolved` → **final=`control`** ⬅FLAGGED
  - **Arm 2: Granisetron + Dexamethasone (Day 1), Compazine + Placebo (Days 2 & 3)** (TT=1.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`control`** ⬅FLAGGED
  - **Arm 1 (Palonosetron + Dexamethasone + Compazine)** (TT=1.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED
  - **Arm 2 (Granisetron + Dexamethasone + Compazine)** (TT=1.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED
  - **Arm 4 (Palonosetron + Dexamethasone + Compazine + Dexamethasone)** (TT=1.5d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED

### NCT00075816 (PMID 23075175)
- CT.gov: https://clinicaltrials.gov/study/NCT00075816  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/23075175
  - **Arm B (Marrow Transplantation)** (TT=29.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`unresolved` → **final=`control`** ⬅FLAGGED
  - **Arm A (PBSC Transplantation)** (TT=29.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED

### NCT00066703 (PMID 24881463)
- CT.gov: https://clinicaltrials.gov/study/NCT00066703  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/24881463
  - **SOFT Arm A (Tamoxifen alone)** (TT=5.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`unresolved` → **final=`control`** ⬅FLAGGED
  - **TEXT Arm A (GnRH analogue + Tamoxifen)** (TT=14.0d): pipe=`control` · CT.gov=`control`(nan) · PubMed=`control` → **final=`control`** — _"exemestane plus ovarian suppression, as compared with tamoxifen plus ovarian suppression, significantly reduced recurrence."_
  - **SOFT Arm B & C (OFS + Tamoxifen/Exemestane)** (TT=14.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED
  - **TEXT Arm A & B (GnRH analogue + Tamoxifen/Exemestane)** (TT=14.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED
  - **TEXT Arm A (GnRH analogue plus Tamoxifen)** (TT=14.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"exemestane plus ovarian suppression, as compared with tamoxifen plus ovarian suppression, significantly reduced recurrence."_
  - **TEXT Arm B (GnRH analogue plus Exemestane)** (TT=14.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`intervention` → **final=`intervention`** — _"adjuvant treatment with exemestane plus ovarian suppression... significantly reduced recurrence."_

### NCT00310180 (PMID 26412349)
- CT.gov: https://clinicaltrials.gov/study/NCT00310180  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/26412349
  - **Arm B (Hormonal Therapy Alone)** (TT=4.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`control`** ⬅FLAGGED
  - **Arm C (Chemotherapy + Hormonal Therapy)** (TT=8.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED

### NCT00134030 (PMID 27569442)
- CT.gov: https://clinicaltrials.gov/study/NCT00134030  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/27569442
  - **Arm A & C (MAP - Control)** (TT=41.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** — _"either postoperative cisplatin, doxorubicin, and methotrexate (MAP) or MAP plus ifosfamide and etoposide (MAPIE)... results define standard of care."_
  - **Arm B (MAP + Pegylated Interferon alfa-2b)** (TT=56.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED
  - **Arm D (MAP + Ifosfamide/Etoposide)** (TT=61.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"do not support the addition of ifosfamide and etoposide to postoperative chemotherapy... associated with increased toxicity."_

### NCT00569127 (PMID 28384065)
- CT.gov: https://clinicaltrials.gov/study/NCT00569127  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/28384065
  - **Arm 2 (Depot Octreotide Plus Interferon Alpha-2b)** (TT=18.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`control`** ⬅FLAGGED
  - **Arm 1 (Depot Octreotide Plus Bevacizumab)** (TT=18.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED

### NCT00565851 (PMID 28438473)
- CT.gov: https://clinicaltrials.gov/study/NCT00565851  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/28438473
  - **Arm I/V (No Surgery + Chemotherapy)** (TT=29.0d): pipe=`control` · CT.gov=`control`(nan) · PubMed=`control` → **final=`control`** — _"randomly assigned (1:1) to standard chemotherapy (six 3-weekly cycles of paclitaxel and carboplatin) or the same chemotherapy regimen plus bevacizumab."_
  - **Arm III/VII (Surgery + CT/GC)** (TT=31.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`control`** ⬅FLAGGED
  - **Arm IV/VIII (Surgery + Chemotherapy + Bevacizumab)** (TT=36.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED
  - **Arm II (Carboplatin + Paclitaxel + Bevacizumab)** (TT=36.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"The addition of bevacizumab to standard chemotherapy, followed by maintenance therapy until progression, improved the median overall survival."_
  - **Arm IV (Surgery + Carboplatin + Paclitaxel + Bevacizumab)** (TT=34.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED

### NCT00265850 (PMID 28632865)
- CT.gov: https://clinicaltrials.gov/study/NCT00265850  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/28632865
  - **Arm A (Bevacizumab + FOLFOX/FOLFIRI)** (TT=27.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`unresolved` → **final=`control`** ⬅FLAGGED
  - **Arm B (Cetuximab + FOLFOX/FOLFIRI)** (TT=53.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED

### NCT01067144 (PMID 29238824)
- CT.gov: https://clinicaltrials.gov/study/NCT01067144  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/29238824
  - **Placebo Arm** (TT=3.0d): pipe=`control` · CT.gov=`control`(PLACEBO_COMPARATOR) · PubMed=`control` → **final=`control`** — _"Gabapentin... or active placebo (lorazepam, 0.5 mg) preoperatively followed by inactive placebo postoperatively."_
  - **Observational Arm** (TT=3.0d): pipe=`control` · CT.gov=`control`(nan) · PubMed=`unresolved` → **final=`control`** ⬅FLAGGED
  - **Gabapentin Arm** (TT=3.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"To determine the effect of perioperative gabapentin on remote postoperative time to pain resolution and opioid cessation."_

### NCT01706939 (PMID 31345387)
- CT.gov: https://clinicaltrials.gov/study/NCT01706939  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/31345387
  - **Arm B (Standard Dose Radiation + Carboplatin)** (TT=48.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** — _"randomized 1:2 to sdCRT (7000 cGy) or rdCRT (5600 cGy) with weekly carboplatin"_
  - **Arm C (Non-responders: Standard CRT + Carboplatin + Erbitux + Paclitaxel)** (TT=48.0d): pipe=`control` · CT.gov=`control`(nan) · PubMed=`unresolved` → **final=`control`** ⬅FLAGGED
  - **Arm A (Reduced Dose Radiation + Carboplatin)** (TT=43.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"after induction chemotherapy (IC), reduced dose chemoradiation (rdCRT) would result in equivalent PFS and OS compared to sdCRT"_

### NCT00127205 (PMID 31693129)
- CT.gov: https://clinicaltrials.gov/study/NCT00127205  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/31693129
  - **Arm 2 (Clodronate)** (TT=8.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`unresolved` → **final=`control`** ⬅FLAGGED
  - **Arm 1 (Zoledronic Acid)** (TT=8.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED
  - **Arm 3 (Ibandronate)** (TT=8.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED
  - **Arm 3 (Ibandronate)** (TT=8.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED

### NCT02625610 (PMID 33197226)
- CT.gov: https://clinicaltrials.gov/study/NCT02625610  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/33197226
  - **Best Supportive Care (BSC) Only** (TT=20.0d): pipe=`control` · CT.gov=`control`(nan) · PubMed=`unresolved` → **final=`control`** ⬅FLAGGED
  - **Chemotherapy Maintenance (Oxaliplatin + 5-FU)** (TT=27.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`control` → **final=`control`** — _"randomly assigned 1:1 to avelumab 10 mg/kg every 2 weeks or continued chemotherapy"_
  - **Avelumab Maintenance** (TT=27.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"We investigated avelumab (anti-programmed death ligand-1 [PD-L1]) maintenance after first-line induction chemotherapy"_

### NCT03141177 (PMID 33657295)
- CT.gov: https://clinicaltrials.gov/study/NCT03141177  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/33657295
  - **Arm C (Sunitinib)** (TT=18.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** — _"Nivolumab plus Cabozantinib versus Sunitinib for Advanced Renal-Cell Carcinoma"_
  - **Arm B (Nivolumab + Ipilimumab + Cabozantinib)** (TT=25.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED
  - **Arm A (Nivolumab + Cabozantinib)** (TT=27.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"we randomly assigned adults with previously untreated clear-cell, advanced renal-cell carcinoma to receive either nivolumab plus cabozantinib"_

### NCT02445391 (PMID 34092112)
- CT.gov: https://clinicaltrials.gov/study/NCT02445391  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/34092112
  - **Arm A (Observation)** (TT=4.0d): pipe=`control` · CT.gov=`control`(NO_INTERVENTION) · PubMed=`unresolved` → **final=`control`** ⬅FLAGGED
  - **Arm B (Platinum-based chemotherapy)** (TT=8.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"iDFS would not be inferior but improved in patients with basal subtype TNBC treated with adjuvant platinum compared with capecitabine"_
  - **Arm C (Capecitabine)** (TT=10.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"high-risk for recurrence, which is reduced by adjuvant capecitabine ... assuming a 4-year iDFS of 67% with capecitabine"_

### NCT00549848 (PMID 34170389)
- CT.gov: https://clinicaltrials.gov/study/NCT00549848  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/34170389
  - **Arm B (Conventional Dose PEG-asparaginase, Standard/High-Risk)** (TT=79.5d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`control` → **final=`control`** — _"randomized in continuation to receive 2500 IU/m2 or 3500 IU/m2 IV ... continuously (15 doses) on the standard/high risk (SHR) arms"_
  - **Arm A (Higher Dose PEG-asparaginase, Standard/High-Risk)** (TT=78.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`intervention` → **final=`intervention`** — _"randomized in continuation to receive 2500 IU/m2 or 3500 IU/m2 IV ... continuously (15 doses) on the standard/high risk (SHR) arms"_
  - **Low-Risk (LR)** (TT=78.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED

### NCT01459497 (PMID 34383006)
- CT.gov: https://clinicaltrials.gov/study/NCT01459497  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/34383006
  - **Arm B (Conventional radiation)** (TT=34.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`nan` → **final=`control`** ⬅FLAGGED
  - **Arm A (Accelerated hypofractionated IGRT)** (TT=19.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`nan` → **final=`intervention`** ⬅FLAGGED

### NCT00500890 (PMID 34997889)
- CT.gov: https://clinicaltrials.gov/study/NCT00500890  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/34997889
  - **Carboplatin Arm (Carboplatin, Etoposide, Vincristine)** (TT=33.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED
  - **Cyclophosphamide Arm (Cyclophosphamide, Etoposide, Vincristine)** (TT=33.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED

### NCT02998528 (PMID 35403841)
- CT.gov: https://clinicaltrials.gov/study/NCT02998528  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/35403841
  - **Arm B (Platinum-Doublet Chemotherapy)** (TT=12.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** — _"to receive nivolumab plus platinum-based chemotherapy or platinum-based chemotherapy alone, followed by resection"_
  - **Arm A (Nivolumab plus Ipilimumab)** (TT=9.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED
  - **Arm C (Nivolumab plus Platinum-Doublet Chemotherapy)** (TT=12.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"neoadjuvant nivolumab plus chemotherapy resulted in significantly longer event-free survival ... than chemotherapy alone"_

### NCT03336333 (PMID 35810754)
- CT.gov: https://clinicaltrials.gov/study/NCT03336333  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/35810754
  - **Arm B (Bendamustine + Rituximab)** (TT=17.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`control` → **final=`control`** — _"randomly assigned patients without del(17)(p13.1) to zanubrutinib (group A) or bendamustine-rituximab (group B)"_
  - **Arm A/C (Zanubrutinib)** (TT=11.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"Zanubrutinib is a next-generation, selective Bruton tyrosine kinase inhibitor ... We compared zanubrutinib with bendamustine-rituximab"_
  - **Arm D (Venetoclax + Zanubrutinib)** (TT=17.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED

### NCT03748641 (PMID 36952634)
- CT.gov: https://clinicaltrials.gov/study/NCT03748641  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/36952634
  - **Placebo + Abiraterone Acetate + Prednisone (AAP)** (TT=18.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`control` → **final=`control`** — _"Patients were assigned 1:1 to receive niraparib + AAP or placebo + AAP"_
  - **Niraparib + Abiraterone Acetate + Prednisone (AAP)** (TT=18.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"Combination treatment with niraparib + AAP significantly lengthened rPFS in patients with HRR+ mCRPC compared with standard-of-care AAP"_
  - **Arm C (Cohort 3: FDC Niraparib/AA + Prednisone)** (TT=18.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED

### NCT04248829 (PMID 37379502)
- CT.gov: https://clinicaltrials.gov/study/NCT04248829  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/37379502
  - **Gefitinib 250 mg** (TT=13.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`control` → **final=`control`** — _"Patients were randomly assigned 1:1 to lazertinib 240 mg once daily orally or gefitinib 250 mg once daily orally"_
  - **Lazertinib 240 mg** (TT=13.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`intervention` → **final=`intervention`** — _"Lazertinib is a potent, CNS-penetrant, third-generation epidermal growth factor receptor (EGFR) tyrosine kinase inhibitor"_
  - **Open-label Lazertinib 240 mg (Cross-over)** (TT=13.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED

### NCT04177108 (PMID 38060199)
- CT.gov: https://clinicaltrials.gov/study/NCT04177108  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/38060199
  - **Arm C (Paclitaxel + Placebo + Placebo)** (TT=40.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`control` → **final=`control`** — _"Grade ≥3 adverse events were more frequent with the triplet than with doublets or single-agent paclitaxel"_
  - **Arm A (Ipatasertib + Atezolizumab + Paclitaxel)** (TT=40.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"Triplet therapy comprised intravenous atezolizumab ... oral ipatasertib ... and intravenous paclitaxel ... as first-line therapy"_
  - **Arm B (Ipatasertib + Paclitaxel / Atezolizumab + Paclitaxel)** (TT=41.5d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED
  - **Arm B - Cohort 2 (Atezolizumab + Paclitaxel + Placebo)** (TT=40.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED

### NCT02864251 (PMID 38252907)
- CT.gov: https://clinicaltrials.gov/study/NCT02864251  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/38252907
  - **Arm C (Pemetrexed plus Platinum)** (TT=18.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** — _"randomly assigned 1:1 to nivolumab ... plus platinum-doublet chemotherapy ... or platinum-doublet chemotherapy alone"_
  - **Arm A (Nivolumab plus Pemetrexed/Platinum)** (TT=18.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"evaluated nivolumab plus chemotherapy versus chemotherapy in patients with EGFR-mutated metastatic non-small-cell lung cancer"_
  - **Arm B (Nivolumab plus Ipilimumab)** (TT=27.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`unresolved` → **final=`intervention`** ⬅FLAGGED

## 3. CORRECTION APPLIED — pipeline label was overridden by the PubMed-arbitrated gold standard; verify

### NCT00295646 (PMID 19213681)
- CT.gov: https://clinicaltrials.gov/study/NCT00295646  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/19213681
  - **Arm A (Nolvadex alone)** (TT=3.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** — _"addition of zoledronic acid to endocrine therapy, as compared with endocrine therapy without zoledronic acid"_
  - **Arm C (Arimidex alone)** (TT=3.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** — _"addition of zoledronic acid to endocrine therapy, as compared with endocrine therapy without zoledronic acid"_
  - **Arm C (Arimidex alone)** (TT=3.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"addition of zoledronic acid to endocrine therapy, as compared with endocrine therapy without zoledronic acid"_
  - **Arm B (Nolvadex plus zoledronate)** (TT=3.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`intervention` → **final=`intervention`** — _"The addition of zoledronic acid to adjuvant endocrine therapy improves disease-free survival"_
  - **Arm D (Arimidex plus zoledronate)** (TT=8.5d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`intervention` → **final=`intervention`** — _"The addition of zoledronic acid to adjuvant endocrine therapy improves disease-free survival"_

### NCT00075829 (PMID 21962393)
- CT.gov: https://clinicaltrials.gov/study/NCT00075829  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/21962393
  - **Arm B2 (Auto-Auto + Observation)** (TT=36.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** — _"allogeneic HSCT ... compared with tandem autologous HSCT"_
  - **Arm A (Auto-Allo: ASCT followed by NMSCT)** (TT=45.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`intervention` → **final=`intervention`** — _"we aimed to assess effectiveness of allogeneic HSCT with non-myeloablative conditioning after autologous HSCT compared with tandem autologous HSCT"_
  - **Arm B1 (Auto-Auto + Maintenance)** (TT=51.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"allogeneic HSCT ... compared with tandem autologous HSCT"_

### NCT00553358 (PMID 22257673)
- CT.gov: https://clinicaltrials.gov/study/NCT00553358  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/22257673
  - **Lapatinib alone** (TT=21.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"the two anti-HER2 agents given together would be better than single-agent therapy"_
  - **Trastuzumab alone** (TT=22.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"pCR rate was significantly higher in the group given lapatinib and trastuzumab ... than in the group given trastuzumab alone"_
  - **Lapatinib + Trastuzumab** (TT=22.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"pCR rate was significantly higher in the group given lapatinib and trastuzumab"_

### NCT00066573 (PMID 23358971)
- CT.gov: https://clinicaltrials.gov/study/NCT00066573  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/23358971
  - **Arm 2: Exemestane + Placebo** (TT=5.0d): pipe=`control` · CT.gov=`control`(nan) · PubMed=`intervention` → **final=`intervention`** ⬅FLAGGED — _"exemestane ... could prove superior to anastrozole regarding efficacy and toxicity"_
  - **Arm 4: Anastrozole + Placebo** (TT=5.0d): pipe=`control` · CT.gov=`control`(nan) · PubMed=`control` → **final=`control`** — _"exemestane ... could prove superior to anastrozole"_
  - **Arm 1: Exemestane + Celecoxib** (TT=5.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"exemestane ... could prove superior to anastrozole regarding efficacy and toxicity"_
  - **Arm 3: Anastrozole + Celecoxib** (TT=5.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"exemestane ... could prove superior to anastrozole"_

### NCT00093795 (PMID 23940225)
- CT.gov: https://clinicaltrials.gov/study/NCT00093795  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/23940225
  - **Group 1 (TAC)** (TT=11.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** — _"whether the incorporation of a fourth drug could improve outcomes relative to two standard regimens"_
  - **Group 2 (DD AC -> P)** (TT=13.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"incorporation of a fourth drug could improve outcomes relative to two standard regimens"_
  - **Group 3 (DD AC -> PG)** (TT=13.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"DD AC->P with four cycles of gemcitabine (G) added to the DD paclitaxel (DD AC->PG)"_

### NCT01998880 (PMID 24401022)
- CT.gov: https://clinicaltrials.gov/study/NCT01998880  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/24401022
  - **Arm C (Clb: Chlorambucil alone)** (TT=15.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** — _"obinutuzumab-chlorambucil or rituximab-chlorambucil, as compared with chlorambucil monotherapy, increased response rates"_
  - **Arm B (RClb: Rituximab + Chlorambucil)** (TT=15.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"obinutuzumab was superior to rituximab when each was combined with chlorambucil"_
  - **Arm A (GClb: Obinutuzumab + Chlorambucil)** (TT=17.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"We investigated the benefit of the type 2, glycoengineered antibody obinutuzumab... as compared with that of rituximab"_

### NCT01156142 (PMID 24733799)
- CT.gov: https://clinicaltrials.gov/study/NCT01156142  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/24733799
  - **Doxepin then Placebo Crossover** (TT=11.0d): pipe=`intervention` · CT.gov=`control`(PLACEBO_COMPARATOR) · PubMed=`intervention` → **final=`intervention`** — _"to test the efficacy of doxepin hydrochloride in the reduction of radiotherapy-induced OM pain"_
  - **Placebo then Doxepin Crossover** (TT=11.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"patients were randomly allocated to a doxepin oral rinse or a placebo"_

### NCT00078949 (PMID 25267740)
- CT.gov: https://clinicaltrials.gov/study/NCT00078949  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/25267740
  - **Arm S2 (DHAP +/- Rituximab)** (TT=9.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`control` → **final=`control`** — _"gemcitabine-based therapy before autologous stem-cell transplantation (ASCT) is as effective as and less toxic than standard treatment"_
  - **Arm S1 (GDP)** (TT=9.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"we hypothesized that gemcitabine-based therapy before autologous stem-cell transplantation (ASCT) is as effective as and less toxic than standard treatment"_
  - **Arm S2 (DHAP)** (TT=20.5d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"treatment with GDP is associated with a noninferior response rate... less toxicity and hospitalization"_

### NCT00006237 (PMID 25332243)
- CT.gov: https://clinicaltrials.gov/study/NCT00006237  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/25332243
  - **Arm 1 (High-Dose Interferon Alpha-2b)** (TT=29.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** — _"High-dose interferon (IFN) for 1 year (HDI) is the US Food and Drug Administration-approved adjuvant therapy"_
  - **Arm 2 (Biochemotherapy: CVD + IL-2 + IFN + G-CSF)** (TT=49.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"We sought to determine whether a shorter course of biochemotherapy would be more effective"_
  - **Arm 1 (One Year High-Dose Interferon Alpha-2b)** (TT=164.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"High-dose interferon (IFN) for 1 year (HDI) is the US Food and Drug Administration-approved adjuvant therapy"_

### NCT00070564 (PMID 25422488)
- CT.gov: https://clinicaltrials.gov/study/NCT00070564  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/25422488
  - **Arm 5 (AC q2w x 4 -> Paclitaxel q2w x 6)** (TT=22.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"that paclitaxel once per week was superior to six cycles of paclitaxel once every 2 weeks"_
  - **Arm 6 (AC q2w x 4 -> Paclitaxel weekly x 12)** (TT=22.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"that paclitaxel once per week was superior to six cycles of paclitaxel once every 2 weeks"_

### NCT00929695 (PMID 25682602)
- CT.gov: https://clinicaltrials.gov/study/NCT00929695  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/25682602
  - **Higher-dose prednisone (1 or 2 mg/kg/day)** (TT=14.5d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`control` → **final=`control`** — _"a 50% decrease in the initial dose of prednisone... would suffice to control graft-versus-host disease"_
  - **Lower-dose prednisone (0.5 or 1 mg/kg/day)** (TT=15.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`intervention` → **final=`intervention`** — _"prednisone is effective and safe for patients with newly diagnosed acute graft-versus-host disease"_
  - **Higher-dose prednisone (1 or 2 mg/kg/day)** (TT=16.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"a 50% decrease in the initial dose of prednisone... would suffice to control graft-versus-host disease"_

### NCT00507416 (PMID 26056177)
- CT.gov: https://clinicaltrials.gov/study/NCT00507416  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/26056177
  - **VD (VELCADE and Dexamethasone)** (TT=53.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"VTD and VMP did not appear to offer an advantage over VD in transplantation-ineligible patients"_
  - **VTD (VELCADE, Thalidomide, and Dexamethasone)** (TT=53.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"VTD and VMP did not appear to offer an advantage over VD"_
  - **VMP (VELCADE, Melphalan, and Prednisone)** (TT=53.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"VTD and VMP did not appear to offer an advantage over VD"_

### NCT01308580 (PMID 28809610)
- CT.gov: https://clinicaltrials.gov/study/NCT01308580  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/28809610
  - **Arm B (Cabazitaxel 25 mg/m²)** (TT=20.0d): pipe=`control` · CT.gov=`control`(nan) · PubMed=`control` → **final=`control`** — _"noninferiority of cabazitaxel 20 mg/m2 (C20) versus C25... the Currently Approved Dose (25 mg/m2)"_
  - **Arm A (Cabazitaxel 20 mg/m²)** (TT=20.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"assessed the noninferiority of cabazitaxel 20 mg/m2 (C20) versus C25 in postdocetaxel patients with mCRPC"_
  - **Arm B (Cabazitaxel 25 mg/m² + Prednisone)** (TT=20.5d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"the Currently Approved Dose (25 mg/m2)... C20 maintained >=50% of the OS benefit of C25"_

### NCT00553410 (PMID 29158011)
- CT.gov: https://clinicaltrials.gov/study/NCT00553410  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/29158011
  - **Arm A (Continuous Letrozole)** (TT=2.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** — _"Extended adjuvant intermittent letrozole versus continuous letrozole in postmenopausal women with breast cancer"_
  - **Arm A (Continuous letrozole)** (TT=2.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"Extended adjuvant intermittent letrozole versus continuous letrozole in postmenopausal women with breast cancer"_
  - **Arm B (Intermittent letrozole)** (TT=2.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"Extended adjuvant intermittent letrozole versus continuous letrozole in postmenopausal women with breast cancer"_

### NCT00946712 (PMID 29169877)
- CT.gov: https://clinicaltrials.gov/study/NCT00946712  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/29169877
  - **Arm 1b (Carboplatin/Paclitaxel)** (TT=12.0d): pipe=`control` · CT.gov=`control`(nan) · PubMed=`control` → **final=`control`** — _"either with cetuximab (...cetuximab group) or without (control group)"_
  - **Arm 1a (Carboplatin/Paclitaxel/Bevacizumab)** (TT=18.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`control` → **final=`control`** — _"either with cetuximab (...cetuximab group) or without (control group)"_
  - **Arm 1a (Carboplatin/Paclitaxel/Bevacizumab)** (TT=53.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"either with cetuximab (...cetuximab group) or without (control group)"_
  - **Arm 2a (Carboplatin/Paclitaxel/Bevacizumab/Cetuximab)** (TT=53.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"explore the activity of cetuximab with chemotherapy in patients with advanced NSCLC who are EGFR FISH-positive"_
  - **Arm 2b (Carboplatin/Paclitaxel/Cetuximab)** (TT=52.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`intervention` → **final=`intervention`** — _"explore the activity of cetuximab with chemotherapy in patients with advanced NSCLC who are EGFR FISH-positive"_

### NCT00118209 (PMID 30939090)
- CT.gov: https://clinicaltrials.gov/study/NCT00118209  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/30939090
  - **Arm A (R-CHOP)** (TT=11.5d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"compared dose-adjusted ... (DA-EPOCH-R) with standard rituximab, cyclophosphamide, doxorubicin, vincristine, and prednisone (R-CHOP)"_
  - **Arm A (R-CHOP)** (TT=41.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"compared dose-adjusted ... (DA-EPOCH-R) with standard rituximab, cyclophosphamide, doxorubicin, vincristine, and prednisone (R-CHOP)"_
  - **Arm B (DA-EPOCH-R)** (TT=40.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"the more intensive, infusional DA-EPOCH-R was more toxic and did not improve PFS or OS compared with R-CHOP"_

### NCT00567567 (PMID 31454045)
- CT.gov: https://clinicaltrials.gov/study/NCT00567567  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/31454045
  - **Regimen A (Single Myeloablative Consolidation)** (TT=93.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"To determine if tandem autologous transplant improves event-free survival (EFS) compared with single transplant"_
  - **Regimen B (Tandem Myeloablative Consolidation)** (TT=110.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"To determine if tandem autologous transplant improves event-free survival (EFS) compared with single transplant"_

### NCT01435018 (PMID 32145827)
- CT.gov: https://clinicaltrials.gov/study/NCT01435018  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/32145827
  - **Arm 1C (Paclitaxel plus ART)** (TT=14.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** — _"or intravenous paclitaxel (the control arm), together with antiretroviral therapy (ART)"_
  - **Etoposide plus ART (ET+ART)** (TT=25.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** ⬅FLAGGED — _"either intravenous bleomycin and vincristine or oral etoposide (the investigational arms)"_
  - **Arm 1A (Etoposide plus ART)** (TT=14.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`intervention` → **final=`intervention`** — _"either intravenous bleomycin and vincristine or oral etoposide (the investigational arms)"_
  - **Arm 1B (Bleomycin and vincristine plus ART)** (TT=14.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"either intravenous bleomycin and vincristine or oral etoposide (the investigational arms)"_

### NCT00408005 (PMID 32813610)
- CT.gov: https://clinicaltrials.gov/study/NCT00408005  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/32813610
  - **Arm A (Capizzi MTX - Control)** (TT=51.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`control` → **final=`control`** — _"5-year disease-free survival (DFS) rates for patients ... randomly assigned to nelarabine (n = 323) and no nelarabine"_
  - **Arm C (High Dose MTX)** (TT=52.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"patients ... randomly assigned to nelarabine ... and no nelarabine (n = 336)"_
  - **Arm B (Capizzi MTX + Nelarabine)** (TT=73.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`intervention` → **final=`intervention`** — _"addition of nelarabine to ABFM therapy improved DFS for children and young adults with newly diagnosed T-ALL"_
  - **Arm D (High Dose MTX + Nelarabine)** (TT=74.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`intervention` → **final=`intervention`** — _"Patients treated with the best-performing arm, C-MTX plus nelarabine ... addition of nelarabine ... improved DFS"_

### NCT01509612 (PMID 33010094)
- CT.gov: https://clinicaltrials.gov/study/NCT01509612  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/33010094
  - **Arm 2 (Placebo Homeopathic Treatment)** (TT=6.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** — _"additive homeopathic treatment compared with placebo in patients with stage IV NSCLC"_
  - **Arm 3 (Standard Care Control)** (TT=5.0d): pipe=`control` · CT.gov=`control`(NO_INTERVENTION) · PubMed=`control` → **final=`control`** — _"52 control patients without any homeopathic treatment were observed for survival only"_
  - **Arm 1 (Verum Homeopathic Treatment)** (TT=6.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`intervention` → **final=`intervention`** — _"received either individualized homeopathic remedies (n = 51) or placebo ... QoL improved significantly in the homeopathy group"_
  - **Arm 2 (Placebo Homeopathic Treatment)** (TT=6.0d): pipe=`intervention` · CT.gov=`control`(PLACEBO_COMPARATOR) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"additive homeopathic treatment compared with placebo in patients with stage IV NSCLC"_

### NCT00063999 (PMID 33078978)
- CT.gov: https://clinicaltrials.gov/study/NCT00063999  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/33078978
  - **Regimen II (Carboplatin/Paclitaxel)** (TT=24.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** ⬅FLAGGED — _"studied carboplatin plus paclitaxel (TC) as a noninferior alternative to TAP"_
  - **Regimen II (Carboplatin/Paclitaxel)** (TT=38.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`intervention` → **final=`intervention`** ⬅FLAGGED — _"studied carboplatin plus paclitaxel (TC) as a noninferior alternative to TAP"_
  - **Regimen I (Doxorubicin/Cisplatin/Paclitaxel + G-CSF)** (TT=31.0d): pipe=`intervention` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"carboplatin plus paclitaxel (TC) as a noninferior alternative to TAP [paclitaxel-doxorubicin-cisplatin]"_

### NCT01150045 (PMID 33821899)
- CT.gov: https://clinicaltrials.gov/study/NCT01150045  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/33821899
  - **Arm A (12 cycles FOLFOX + Placebo)** (TT=11.0d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** — _"addition of celecoxib for 3 years, compared with placebo, to standard adjuvant chemotherapy"_
  - **Arm A (12 cycles of FOLFOX + placebo daily)** (TT=15.5d): pipe=`control` · CT.gov=`control`(ACTIVE_COMPARATOR) · PubMed=`control` → **final=`control`** — _"addition of celecoxib for 3 years, compared with placebo, to standard adjuvant chemotherapy"_
  - **Arm C (6 cycles FOLFOX + Placebo)** (TT=10.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"addition of celecoxib for 3 years, compared with placebo, to standard adjuvant chemotherapy"_
  - **Arm D (6 cycles FOLFOX + Celecoxib)** (TT=15.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"addition of celecoxib to adjuvant chemotherapy with fluorouracil, leucovorin, and oxaliplatin (FOLFOX)"_
  - **Arm B (12 cycles FOLFOX + Celecoxib)** (TT=14.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"addition of celecoxib to adjuvant chemotherapy with fluorouracil, leucovorin, and oxaliplatin (FOLFOX)"_

### NCT00295620 (PMID 34320285)
- CT.gov: https://clinicaltrials.gov/study/NCT00295620  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/34320285
  - **Arm B (Anastrozole 5 years)** (TT=2.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** ⬅FLAGGED — _"anastrozole for an additional 2 years ... or an additional 5 years (5-year group, receiving a total of 10 years)"_
  - **Arm A (Anastrozole 2 years)** (TT=2.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"extending hormone therapy by 5 years provided no benefit over a 2-year extension"_

### NCT01949337 (PMID 36996380)
- CT.gov: https://clinicaltrials.gov/study/NCT01949337  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/36996380
  - **Arm A (Enzalutamide)** (TT=16.5d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`control` → **final=`control`** — _"whether the addition of abiraterone acetate and prednisone (AAP) to enzalutamide prolongs overall survival"_
  - **Arm A (Enzalutamide alone)** (TT=17.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"whether the addition of abiraterone acetate and prednisone (AAP) to enzalutamide prolongs overall survival"_
  - **Arm B (Enzalutamide, Abiraterone, and Prednisone)** (TT=17.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"whether the addition of abiraterone acetate and prednisone (AAP) to enzalutamide prolongs overall survival"_

### NCT03419403 (PMID 37257422)
- CT.gov: https://clinicaltrials.gov/study/NCT03419403  ·  PubMed: https://pubmed.ncbi.nlm.nih.gov/37257422
  - **Arm A (Standard Steroids)** (TT=53.0d): pipe=`control` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"randomized (1:1:1) to OSE prophylactic treatments ... (a) standard steroid eye drops"_
  - **Arm A (Standard Steroids)** (TT=53.0d): pipe=`intervention` · CT.gov=`intervention`(nan) · PubMed=`control` → **final=`control`** ⬅FLAGGED — _"randomized (1:1:1) to OSE prophylactic treatments ... (a) standard steroid eye drops"_
  - **Arm B (Standard Steroids + Vasoconstrictor + Cold Compress)** (TT=53.0d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"(b) standard steroid eye drops plus vasoconstrictor eye drops and cold compress"_
  - **Arm C (Enhanced Steroids + Vasoconstrictor + Cold Compress)** (TT=58.5d): pipe=`intervention` · CT.gov=`intervention`(EXPERIMENTAL) · PubMed=`intervention` → **final=`intervention`** — _"(c) enhanced steroids plus vasoconstrictor eye drops and cold compress"_
