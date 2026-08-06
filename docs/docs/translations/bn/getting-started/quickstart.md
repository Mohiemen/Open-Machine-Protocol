# কুইকস্টার্ট - ১৫ মিনিটে একটি লাইভ ফ্যাক্টরি ফ্লোর, কোনো হার্ডওয়্যার ছাড়াই

| | |
|---|---|
| **অবস্থা** | খসড়া (ইংরেজি মূল: [quickstart.md](../../../getting-started/quickstart.md)) |
| **অবস্থান** | docs/translations/bn/getting-started/quickstart.md |
| **যা লাগবে** | Python 3.11+ সহ একটি ল্যাপটপ, ১৫ মিনিট। কোনো মেশিন লাগবে না, Raspberry Pi লাগবে না, ক্লাউড অ্যাকাউন্টও লাগবে না। |
| **যা পাবেন** | ১০টি মেশিনের একটি সিমুলেটেড সুইং লাইন, যা স্ট্যান্ডার্ড ও যাচাইযোগ্য ডেটা একটি লাইভ ড্যাশবোর্ডে পাঠাবে - এবং প্রতিটি অংশ কীভাবে কাজ করে তার ধারণা। |

> **অনুবাদ নোট**: কমান্ড, ফিল্ডের নাম, ও আইডেন্টিফায়ার ইংরেজিতেই থাকে -
> সেগুলো কোড। ব্যাখ্যার ভাষা বাংলা।

---

## ১. ইনস্টল

```bash
git clone https://github.com/Mohiemen/Open-Machine-Protocol
cd Open-Machine-Protocol
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ./gateway -e ./tools
```

কাজ করেছে কি না দেখুন:

```bash
omp-validate --version
omp-simulate --version
```

## ২. আপনার প্রথম OMP মেসেজ (২ মিনিট)

একটি সিমুলেটেড সুইং মেশিন চালিয়ে দেখুন কী বের হয়:

```bash
omp-simulate --profile textile-sewing --machines 1 --duration 10s
```

স্ক্রিনে NDJSON envelope স্ক্রল হতে দেখবেন। একটি নিয়ে পড়ুন:

```json
{
  "omp_version": "0.1.0",
  "profile": "textile-sewing/0.1",
  "gateway_id": "gw-sim-01",
  "machine_id": "sim-line1-m01",
  "seq": 14,
  "ts": "2026-07-24T10:02:11.408Z",
  "schema": "event",
  "body": {
    "event_type": "cycle_complete",
    "payload": { "cycle_count": 14, "cycle_time_ms": 31240 }
  },
  "checksum": "9f2a..."
}
```

তিনটি জিনিস লক্ষ করুন - এগুলোই পুরো ধারণার মূল:

- **`profile`** যেকোনো কনজিউমারকে বলে দেয় এই মেশিন ঠিক কোন শব্দভান্ডারে কথা বলছে।
- **`seq`** প্রতি মেশিনে প্রতি মেসেজে এক করে বাড়ে। কোনো কনজিউমার যদি 14-এর পরে 16 দেখে, সে জানে মেসেজ 15 আছে কিন্তু পৌঁছায়নি। অর্থাৎ সম্পূর্ণতা যাচাইযোগ্য।
- **`checksum`** বডিকে সিল করে দেয়। `cycle_count`-এর একটি সংখ্যা বদলালেই মেসেজটি প্রমাণসহ অমিল হয়ে যায়। অর্থাৎ অখণ্ডতা (integrity) যাচাইযোগ্য।

## ৩. স্ট্রিম ভ্যালিডেট করুন (১ মিনিট)

সিমুলেটরের আউটপুট validator-এর মধ্য দিয়ে পাঠান - এটি প্রতিটি envelope-কে core schema **এবং** textile-sewing profile - দুটির বিরুদ্ধেই যাচাই করে:

```bash
omp-simulate --profile textile-sewing --machines 1 --duration 10s | omp-validate
# ✔ 47 messages valid (schema: event x45, machine x1, process_run x1)
```

এবার প্রমাণ করুন ভ্যালিডেশন সত্যিই কামড় দেয় - ইচ্ছা করে নষ্ট করা স্ট্রিম দিন:

```bash
omp-simulate --profile textile-sewing --machines 1 --duration 10s --chaos corrupt-fields | omp-validate
# ✖ seq 23: body.payload.cycle_time_ms expected number, got string
# ✖ seq 31: checksum mismatch
# 45 valid, 2 invalid (details above)
```

আসল গেটওয়েতে এই দুটি মেসেজ dead-letter store-এ যেত - বৈধ ডেটা হিসেবে কখনোই এক্সপোর্ট হতো না। অবৈধ কিছুই নীরবে যাতায়াত করে না।

## ৪. ব্রোকারে স্ট্রিম করুন ও লাইভ দেখুন (৫ মিনিট)

একটি লোকাল MQTT ব্রোকার চালু করুন (যেকোনো একটি):

```bash
# পদ্ধতি A - Docker
docker run -d --name mosquitto -p 1883:1883 eclipse-mosquitto:2 mosquitto -c /mosquitto-no-auth.conf

# পদ্ধতি B - সরাসরি ইনস্টল (Debian/Ubuntu: apt install mosquitto mosquitto-clients)
mosquitto -v
```

এবার পুরো ১০-মেশিনের সিমুলেটেড লাইন MQTT-তে এক্সপোর্ট করুন, সঠিক টপিক স্ট্রাকচারসহ:

```bash
omp-simulate --profile textile-sewing --machines 10 --export mqtt://localhost:1883 --site demo --line line1
```

আরেকটি টার্মিনালে ফ্লোরটি জীবন্ত হয়ে উঠতে দেখুন:

```bash
mosquitto_sub -t 'omp/#' -v
```

আপনি এখন ঠিক সেই wire format দেখছেন যা একটি আসল কারখানা তৈরি করে। টপিক অনুসরণ করে `omp/{site}/{area}/{line}/{machine}/{schema}` - একটি প্ল্যাটফর্ম যেভাবে করত সেভাবে সংকীর্ণভাবে subscribe করুন (`omp/demo/+/line1/+/event`)।

## ৫. একটি ড্যাশবোর্ড (৫ মিনিট)

```bash
cd examples/grafana-dashboards
docker compose up -d      # Grafana + MQTT datasource, আগে থেকে কনফিগার করা
```

ব্রাউজারে http://localhost:3000 খুলুন (admin/admin) - **Sewing Line Overview** ড্যাশবোর্ডে আপনার সিমুলেটেড লাইনের লাইভ cycle count, মেশিনের অবস্থা, বন্ধ হওয়ার কারণ, আর প্রতি মেশিনের cycle time distribution দেখা যাবে।

এই ড্যাশবোর্ড স্ট্যান্ডার্ড OMP মেসেজ ছাড়া আর কিছুই ব্যবহার করে না। পরে একটি আসল গেটওয়ের দিকে তাক করলেও এটি অপরিবর্তিত কাজ করবে। একটি স্ট্যান্ডার্ড ঠিক এটাই কিনে দেয়।

## ৬. যা শিখলেন, বাস্তব ডিপ্লয়মেন্টে যার মানে যা

| এই কুইকস্টার্টে | আসল কারখানায় |
|---|---|
| `omp-simulate` | Raspberry Pi-তে গেটওয়ে, মেশিনের বিরুদ্ধে অ্যাডাপ্টার চালাচ্ছে |
| সিমুলেটেড মেশিন | Juki নেটওয়ার্ক, Modbus PLC, ESP32 রেট্রোফিট নোড |
| `--chaos corrupt-fields` | বৈদ্যুতিক নয়েজ, খারাপ সিরিয়াল লাইন, অ্যাডাপ্টারের বাগ |
| লোকাল Mosquitto | কারখানার ব্রোকার, বা প্ল্যাটফর্মে সরাসরি REST push |
| Grafana উদাহরণ | আপনার MES, ফ্যাক্টরি OS, বা DPP প্ল্যাটফর্ম - একই টপিক খাচ্ছে |

Envelope, টপিক, ভ্যালিডেশন আচরণ, আর dedup নিয়ম - সব একই। সিমুলেটরের কিছুই খেলনা ফরম্যাট নয়।

## ৭. এরপর কোথায় যাবেন

- **আসল মেশিন আছে?** [Your First Real Machine](../../../getting-started/first-real-machine.md) - generic-serial বা Modbus register map দিয়ে একটি মেশিন যুক্ত করা, Pi-তে গেটওয়ে ইনস্টলসহ। *(অনুবাদ এখনো হয়নি - সাহায্য চাই!)*
- **মেশিনের কোনো ডিজিটাল আউটপুটই নেই?** [Retrofit Installation](../../../guides/retrofit-installation.md) - ESP32 CT clamp যন্ত্রাংশ থেকে স্ট্রিমিং পর্যন্ত এক বিকেলে।
- **প্ল্যাটফর্ম বানাচ্ছেন?** [Platform Ingestion](../../../integrations/platform-ingestion.md) আর [DPP Evidence Chain](../../../integrations/dpp-evidence-chain.md)।
- **অবদান রাখতে চান?** [CONTRIBUTING.md](../../../../CONTRIBUTING.md) - আর কোনো unsupported মেশিনে আপনার access থাকলে, কোড না লিখেও protocol capture-ই প্রজেক্টকে দেওয়া সবচেয়ে মূল্যবান জিনিস।

## সমস্যা হলে

- `omp-simulate: command not found` - venv চালু নেই, অথবা `pip install -e ./tools` ব্যর্থ হয়েছে; আবার চালিয়ে আউটপুট পড়ুন।
- MQTT connection refused - ব্রোকার চলছে না বা পোর্ট 1883 দখলে; `docker logs mosquitto` দেখুন বা `-p 1884:1883` দিয়ে URL ঠিক করুন।
- Grafana-তে ডেটা নেই - আগে মেসেজ আসছে কি না দেখুন (`mosquitto_sub -t 'omp/#'`), তারপর datasource `host.docker.internal:1883`-এর দিকে আছে কি না দেখুন (Linux ব্যবহারকারী - compose ফাইলের কমেন্ট করা network_mode লাইন দেখুন)।
- অন্য কিছু - [FAQ](../../../getting-started/faq.md) (ইংরেজি), তারপর GitHub Discussions। আপনার OS আর হুবহু কমান্ডটি লিখে দিন। বাংলায় প্রশ্ন করতে সংকোচ করবেন না - মেইনটেইনাররা অনুবাদ করে নেবেন; ভালো আইডিয়াটাই আসল, ভাষার পালিশ নয়।
