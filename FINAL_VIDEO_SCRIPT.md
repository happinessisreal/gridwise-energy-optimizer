# GridWise — Complete Final 3-Minute Video Presentation Script
**BUP CSE Fest 2026 Hackathon · Online Preliminary Round**  
*Track: Smart Campus Energy Optimization Challenge (GridWise LLM)*  
*Target Duration: Exactly 2:50 (Safely below the 3:00 / 180s hard disqualification ceiling)*  
*Word Count: ~410 words · Pacing: Confident, crisp, ~140 words/minute*

---

## Storyboard & Timed Delivery Breakdown

```
+---------------------------------------------------------------------------------------------------------+
| Timeline     | Section Name               | Presentation Slide & Visuals                                |
| 0:00 - 0:25  | Challenge & Mission        | Slide 1: Title, Microgrid Dynamics & Team                   |
| 0:25 - 0:55  | 4-Stage Architecture       | Slide 2: Decoupled Pipeline (API -> LLM -> Guard -> Solver) |
| 0:55 - 1:45  | Formula Derivation & Proof | Slide 4: LP Math Formulation, Recurrence Unroll & KKT Proof |
| 1:45 - 2:25  | Benchmarks & Verification  | Slide 5: 10/10 Cases (0.0000 BDT Delta) & 91 Tests Passed   |
| 2:25 - 2:50  | Production & Pre-Submit    | Slide 6: Live Railway, GHCR Docker & Page 11 Checklist      |
| 2:50 - 3:00  | Buffer / Wrap Up           | Buffer for clean outro                                      |
+---------------------------------------------------------------------------------------------------------+
```

---

# Version 1: English Script (Verbatim)

### [0:00 - 0:25] Scene 1: Challenge Dynamics & Microgrid Mission (25s)
**Slide on Screen**: Slide 1 (`presentation.html` / `presentation_v2.pptx`)

> "Honorable judges, welcome to **GridWise**, our solution for the BUP CSE Fest 2026 Smart Campus Energy Optimization Challenge.
> 
> Modern university campuses balance fluctuating rooftop solar, dynamic time-of-use grid tariffs, and battery storage. Crucially, facility managers issue critical operational constraints—such as panel washings, relay tests, and feeder caps—through unstructured natural language notes.
> 
> Our mission: bridge natural language directives with mathematically provable optimization, scheduling a 24-hour battery plan that minimizes electricity cost in BDT while strictly honoring every physical and operational law."

---

### [0:25 - 0:55] Scene 2: Decoupled 4-Stage Pipeline & Zero-Downtime Fallback (30s)
**Slide on Screen**: Slide 2 (Architecture Pipeline)

> "The core philosophy of GridWise is: **never trust generative AI with raw microgrid math**.
> 
> We built a decoupled four-stage pipeline:
> First, our **FastAPI ingestion layer** uses Pydantic v2 to validate relational physics ($E_0 \le \text{Capacity}$) and reject `NaN` or `Inf` floats.
> 
> Second, our **LLM Directive Interpreter** uses zero-shot prompting across DeepSeek-V3, Groq, or OpenAI to extract operational intent while filtering out distractor notes. If external APIs experience latency or rate limits, our built-in offline regex parser engages automatically, guaranteeing **100% uptime with zero crashes**.
> 
> Third, our **Deterministic Guardrail Layer** enforces the invariant: `applies` is false if and only if the directive is a `no_op`, normalizes hours into sorted arrays in $[0..23]$, and converts percentage reserves to kWh."

---

### [0:55 - 1:45] Scene 3: How We Got the Formula & Proof of Global Optimality (50s)
**Slide on Screen**: Slide 4 (Microgrid Physics & Continuous LP Formulation)

> "Now, how did we derive the optimization formula?
> 
> The hourly battery state follows the discrete recurrence: $E[h+1] = E[h] + c[h] - d[h]$.
> By unrolling this recurrence across all 24 hours, cumulative energy becomes:
> $$E[h] = E_0 + \sum_{i=0}^{h-1} (c[i] - d[i])$$
> 
> This unrolling transforms complex battery storage bounds into **48 standard linear inequalities**, while Kirchhoff's campus energy balance forms **24 linear equality constraints**. Crucially, we enforce **end-of-day battery neutrality** via the equality constraint $\sum (c[h] - d[h]) = 0$, guaranteeing $E_{24} = E_0$ so stored energy is not exhausted overnight.
> 
> We formulated this as a continuous Linear Program with **96 decision variables** and solved it using **SciPy's HiGHS dual simplex solver**.
> 
> Why does this guarantee the absolute global minimum?
> Because all 73 constraints are affine, the feasible search space forms a **bounded convex polytope**. In convex optimization, every local minimum is guaranteed to be a **global minimum**—eliminating the local traps of heuristic algorithms.
> HiGHS terminates with **zero KKT duality gap**, and our $+10^{-7} (c[h] + d[h])$ regularizer strictly enforces $c[h] \cdot d[h] = 0$, eliminating battery churn without integer variables."

---

### [1:45 - 2:25] Scene 4: 10/10 Benchmark Verification & Adversarial Hardening (40s)
**Slide on Screen**: Slide 5 (Official Benchmark Table)

> "Let's see the empirical verification.
> 
> Running our automated test harness against all 10 official reference benchmark cases:
> Every operator directive is extracted with 100% precision.
> 
> The solver satisfies every physical constraint, and our calculated electricity cost matches the official reference solutions with **exactly 0.0000 BDT difference across all 10 cases**.
> 
> Furthermore, running our adversarial test suite, all **91 attack vectors pass cleanly**—verifying factor inversions like 'reduced by 80%' to 0.20, noon-crossing time windows, and secret-safe HTTP 500 error sanitization."

---

### [2:25 - 2:50] Scene 5: Production Deployment & Pre-Submit Compliance (25s)
**Slide on Screen**: Slide 6 (Production Readiness & Checklist)

> "GridWise is fully production-ready:
> - Live on Railway: `gridwise-energy-optimizer-production.up.railway.app`
> - Docker image hosted on GitHub Container Registry: `ghcr.io/happinessisreal/gridwise-optimizer:latest`
> - Executes as a secure non-root user (`appuser:10001`) with zero committed secrets.
> - All 10 items in the Participant Guide Page 11 Pre-Submit Checklist are 100% verified.
> 
> GridWise combines intelligent language comprehension with provable mathematical optimization.
> Thank you, BUP CSE Fest and Poridhi.io!"

---
---

# Version 2: Bangla Script (বাংলা ভার্সন)

### [0:00 - 0:25] দৃশ্য ১: পটভূমি ও মাইক্রোগ্রিড মিশন (২৫ সেকেন্ড)
> *"সম্মানিত বিচারকমণ্ডলী, সবাইকে স্বাগত জানাচ্ছি আমাদের প্রজেক্ট **GridWise**-এ — BUP CSE Fest 2026 স্মার্ট ক্যাম্পাস এনার্জি অপটিমাইজেশন চ্যালেঞ্জের জন্য আমাদের সমাধান।*
> 
> *একটি আধুনিক বিশ্ববিদ্যালয় ক্যাম্পাসে ওঠানামা করা রুফটপ সোলার জেনারেশন, ক্যাম্পাসের পরিবর্তনশীল লোড ডিমান্ড এবং পিক-অফপিক গ্রিড ট্যারিফের ভারসাম্য রক্ষা করা অত্যন্ত জটিল। এর ওপর ফ্যাসিলিটি ম্যানেজাররা বিভিন্ন অপারেশনাল নির্দেশনা দেন সাধারণ ভাষায়।*
> 
> *আমাদের মিশন: এই প্রাকৃতিক ভাষার নির্দেশনাগুলোকে নিখুঁত গাণিতিক ফর্মুলেশনে রূপান্তর করে ২৪ ঘণ্টার এমন একটি অপটিমাল ব্যাটারি শিডিউল তৈরি করা, যা বিদ্যুৎ খরচ সর্বনিম্ন রাখবে এবং ক্যাম্পাসের কোনো ফিজিক্যাল নিয়ম ভঙ্গ করবে না।"*

---

### [0:25 - 0:55] দৃশ্য ২: ডিকাপল্ড ৪-স্টেজ পাইপলাইন ও অফলাইন ফলব্যাক (৩০ সেকেন্ড)
> *"আমাদের সিস্টেম আর্কিটেকচারের মূল দর্শন একটাই: **কখনোই জেনারেটিভ এআই-এর ওপর র (raw) মাইক্রোগ্রিড ম্যাথ ছেড়ে দেওয়া যাবে না**।*
> 
> *এজন্য আমরা তৈরি করেছি একটি ডিকাপল্ড চার স্টেজের পাইপলাইন:*
> *প্রথমত, আমাদের **FastAPI ইনজেশন লেয়ার** Pydantic v2 দিয়ে $E_0 \le \text{Capacity}$ চেক করে এবং NaN বা ইনফিনিটি ইনপুট আটকে দেয়।*
> 
> *দ্বিতীয়ত, আমাদের **LLM ডিরেক্টিভ ইন্টারপ্রেটার** DeepSeek-V3, Groq কিংবা OpenAI ব্যবহার করে জিরো-শট প্রম্পটিংয়ের মাধ্যমে অপারেটরের আসল ইনটেন্ট বের করে আনে। কোনো কারণে এক্সটার্নাল এআই সার্ভিসে নেটওয়ার্ক সমস্যা হলে, আমাদের অফলাইন রেজেক্স পার্সার স্বয়ংক্রিয়ভাবে ব্যাকআপ নেয় — যা নিশ্চিত করে **১০০% সিস্টেম আপটাইম এবং জিরো ডাউনটাইম**।*
> 
> *তৃতীয়ত, আমাদের **ডিটারমিনিস্টিক গার্ডরেইল লেয়ার** নিশ্চিত করে মূল গাণিতিক নীতি: `applies` মান false হবে কেবল এবং কেবল যদি ডিরেক্টিভটি একটি `no_op` হয়, এবং টাইম উইন্ডোগুলোকে [০..২৩] ঘণ্টার সর্টেড অ্যারেতে সাজিয়ে নেয়।"*

---

### [0:55 - 1:45] দৃশ্য ৩: ফর্মুলা ডেরিভেশন ও গ্লোবাল অপটিমালিটির গাণিতিক প্রমাণ (৫০ সেকেন্ড)
> *"এখন আসা যাক, কীভাবে আমরা অপটিমাইজেশন ফর্মুলাটি ডেরাইভ করেছি।*
> 
> *ব্যাটারির এনার্জি ডাইনামিক্সের সমীকরণ হলো: $E[h+1] = E[h] + c[h] - d[h]$।*
> *এই সমীকরণটিকে ২৪ ঘণ্টার জন্য আনরোল (unroll) করলে যেকোনো ঘণ্টার কিউমুলেটিভ এনার্জি দাঁড়ায়:*
> $$E[h] = E_0 + \sum_{i=0}^{h-1} (c[i] - d[i])$$
> 
> *এই আনরোলিংয়ের মাধ্যমে আমরা ব্যাটারির জটিল ক্যাপাসিটি এবং ডায়নামিক রিজার্ভ ফ্লোরকে **৪৮টি স্ট্যান্ডার্ড লিনিয়ার অসমতায় (inequality constraints)** রূপান্তর করেছি, এবং ক্যাম্পাসের কার্শফ ব্যালান্স সমীকরণ থেকে পেয়েছি **২৪টি লিনিয়ার সমতা**। পাশাপাশি, আমরা নিশ্চিত করেছি **এন্ড-অফ-ডে ব্যাটারি নিউট্রালিটি** ($\sum (c - d) = 0 \iff E_{24} = E_0$), যাতে ক্যাম্পাসের ব্যাটারি সারা দিনে অপচয় হয়ে রাতে খালি না থাকে।*
> 
> *পুরো সিস্টেমটিকে **৯৬টি ডিসিশন ভেরিয়েবল** দিয়ে একটি কনটিনিউয়াস লিনিয়ার প্রোগ্রাম হিসেবে মডেল করে **SciPy-এর HiGHS সিমপ্লেক্স সলভার** দিয়ে সমাধান করা হয়েছে।*
> 
> *কেন এটি গাণিতিকভাবে পরম গ্লোবাল মিনিমাম নিশ্চিত করে?*
> *কারণ আমাদের ৭৩টি কনস্ট্রেইন্ট মিলে সার্চ স্পেসটিকে একটি **ক্লোজড কনভেক্স পলিটোপে** পরিণত করে। কনভেক্স স্পেসে কোনো লোকাল মিনিমা থাকে না — যেকোনো লোকাল অপটিমামই নিশ্চিতভাবে গ্লোবাল অপটিমাম।*
> *HiGHS সলভার **জিরো KKT ডুয়ালিটি গ্যাপ** দিয়ে টার্মিনেট করে, এবং আমাদের অবজেক্টিভের ক্ষুদ্র $+10^{-7} (c + d)$ টার্মটি নিশ্চিত করে $c[h] \cdot d[h] = 0$, যা কোনো ইন্টিজার ভেরিয়েবল ছাড়াই ব্যাটারির অপ্রয়োজনীয় চর্ন সম্পূর্ণ দূর করে।"*

---

### [1:45 - 2:25] দৃশ্য ৪: ১০/১০ বেঞ্চমার্ক ও অ্যাডভারসারিয়াল ভেরিফিকেশন (৪০ সেকেন্ড)
> *"এবার সরাসরি আমাদের সিস্টেমের ভেরিফিকেশন দেখে নেওয়া যাক।*
> 
> *অফিসিয়াল ১০টি রেফারেন্স স্যাম্পল কেসের ওপর টেস্ট চালিয়ে আমরা দেখতে পাচ্ছি:*
> *প্রতিটি ডিরেক্টিভ ১০০% প্রিসিশন নিয়ে ইন্টারপ্রেট হয়েছে।*
> 
> *সলভার প্রতিটি ফিজিক্যাল কনস্ট্রেইন্ট বজায় রেখেছে, এবং আমাদের অপটিমাইজারের মোট খরচ অফিসিয়াল রেফারেন্স ফলাফলের সাথে **প্রতিটি কেসেই ঠিক ০.০০০০ টাকা (0.0000 BDT) পার্থক্যে নিখুঁতভাবে মিলে গেছে!**
> 
> *পাশাপাশি, আমাদের **৯১টি টেস্ট ভেক্টরের অ্যাডভারসারিয়াল টেস্ট স্যুটের** সবকটিই গ্রিন পাস করেছে — যা প্রমাণ করে 'reduced by 80%' কে ০.২০-এ রূপান্তর, দুপুর ১২টা ও মধ্যরাত অতিক্রমকারী টাইম উইন্ডো এবং সিক্রেট-সেফ এরর হ্যান্ডলিং সম্পূর্ণরূপে অটুট।"*

---

### [2:25 - 2:50] দৃশ্য ৫: প্রোডাকশন ডেপ্লয়মেন্ট ও চেকলিস্ট (২৫ সেকেন্ড)
> *"GridWise সম্পূর্ণ প্রোডাকশন-রেডি:*
> *- লাইভ ক্লাউড এপিআই: `gridwise-energy-optimizer-production.up.railway.app`*
> *- ডকার ইমেজ: `ghcr.io/happinessisreal/gridwise-optimizer:latest`*
> *- নন-রুট ইউজার সিকিউরিটি (`appuser:10001`) এবং কোডবেসে কোনো হার্ডকোডেড সিক্রেট নেই।*
> *- পার্টিসিপ্যান্ট গাইডের পেজ ১১-এর প্রি-সাবমিট চেকলিস্টের ১০টি আইটেমই ১০০% ভেরিফাইড।*
> 
> *বুদ্ধিদীপ্ত ভাষা অনুধাবন এবং নিখুঁত গাণিতিক অপটিমাইজেশনের মেলবন্ধনই হলো GridWise।*
> *ধন্যবাদ BUP CSE Fest এবং Poridhi.io-কে!"*
