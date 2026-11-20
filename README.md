# Shipping Analytics AI Agent — Milestone 2

**Hacktiv8 Applied AI Engineer | Shipping Analytics Agent**

Aplikasi percakapan analitik pengiriman berbasis **Streamlit + FastAPI + OpenAI + Neon PostgreSQL**, dengan **SQL Guard** untuk query read-only dan **SQLite** untuk riwayat percakapan per pengguna.


## 1. Fitur

- Tanya jawab analitik bilingual (Bahasa Indonesia / English).
- Shipment volume, carrier on-time performance, monetary refund rate, destination city analytics, dan weekly shipment trends.
- Perhitungan **weighted overall on-time**: total on-time delivered ÷ total delivered; `in_transit` tidak masuk denominator.
- Refund rate berdasarkan **nominal uang**: jumlah refund ÷ jumlah shipping fee; filter `service_level` (`express` / `standard`) bila disebut.
- Tren mingguan kota Bandung pada Agustus, termasuk follow-up berdasarkan riwayat percakapan.
- Pernyataan keterbatasan untuk periode di luar dataset dan lokasi real-time.
- Perlindungan terhadap perubahan data, permintaan secret, dan instruksi berbahaya yang ditemukan dalam data sumber.
- Bearer-token demo untuk dua akun dan pembatasan akses riwayat percakapan berdasarkan pemilik.

## 2. Arsitektur

```text
Browser / Streamlit UI (:8501)
       | bearer token + conversation messages
       v
FastAPI (:8000) -- Authentication -- SQLite history (persistent volume)
       |
       v
AI request classification / guarded analytics routing
       |
       v
Fixed SQL templates -> SQL Guard -> read-only Neon database role
                                     |
                                     v
                  gold.shipment_fact | gold.carrier_daily | gold.city_daily
       |
       v
Grounded answer + data_basis -> FastAPI -> Streamlit
```

**Prinsip desain:** LLM menginterpretasi permintaan; ia **tidak mendapat wewenang mengeksekusi SQL bebas**. Data numerik berasal dari query template yang divalidasi. Tidak ada vector database atau document-RAG dalam implementasi ini.

## 3. Data & cakupan

- `gold.shipment_fact`: 600 baris.
- `gold.carrier_daily`: 246 baris.
- `gold.city_daily`: 323 baris.
- Tanggal yang dipakai untuk analitik order adalah `order_date` atau `metric_date` turunan order.
- Agustus 2026 memiliki **217 shipment** (C02: 73, C01: 72, C03: 72).
- On-time Agustus: C01 49/65 (75,38%); C02 50/66 (75,76%); C03 50/67 (74,63%); **overall 149/198 = 75,25%**.
- Express, 1–20 September 2026: refund **IDR 28.500** / shipping fees **IDR 798.000** = **3,57%**.

*Angka di atas merupakan hasil verifikasi pada dataset demonstrasi saat pengujian; bukan data operasional real-time.*

## 4. Konfigurasi lingkungan

Gunakan Python 3.12 dan Docker Engine + Docker Compose. Buat `.env` lokal **tanpa meng-commit secret**. Nama environment utama yang digunakan project:

```dotenv
OPENAI_API_KEY=<YOUR_OPENAI_API_KEY>
OPENAI_MODEL=<YOUR_AVAILABLE_MODEL>
GOLD_DATABASE_URL=<NEON_READER_CONNECTION_URL>
```

- `GOLD_DATABASE_URL` sebaiknya menggunakan role Neon **read-only** (`analytics_reader` pada setup demo), bukan role admin.
- Backend menyimpan riwayat ke SQLite. Saat Docker Compose berjalan, path diarahkan ke `/app/data/conversations.sqlite3` melalui `SQLITE_PATH` dan persistent named volume.
- Periksa `src/auth.py` untuk konfigurasi token demo. **Jangan menaruh token dalam README, screenshot, atau repository publik**.
- `compose.yaml` mengekspose service hanya ke loopback host `127.0.0.1` (port 8000 / 8501) untuk pengujian lokal.

## 5. Jalankan dengan Docker

Dari direktori root project:

```bash
docker info --format '{{.ServerVersion}}'
docker compose config --quiet
# Konfigurasi saat ini memakai satu image yang digunakan oleh api dan ui:
docker build -t delivery-agent:local .
docker compose up -d --no-build
docker compose ps
curl http://127.0.0.1:8000/healthz
```

Buka **http://127.0.0.1:8501** untuk Streamlit dan **http://127.0.0.1:8000/docs** untuk Swagger FastAPI. Masukkan token demo yang tersedia secara privat. Hentikan layanan dengan `docker compose down` (volume SQLite akan tetap tersimpan selama tidak menggunakan `-v`).

Untuk memeriksa log bila terjadi error:

```bash
docker compose logs --tail=80 api ui
```

**Catatan:** Dockerfile harus menyertakan `httpx`, yang diimpor oleh `app.py`. Image dengan tag yang sama dipakai oleh kedua container agar tidak bentrok ketika build paralel.

## 6. Jalankan lokal (tanpa Docker)

Aktifkan virtual environment dan pasang dependency project. Dari root project:

```bash
python -m uvicorn src.api:app --reload --host 127.0.0.1 --port 8000
```

Di terminal lain:

```bash
AGENT_API_URL=http://127.0.0.1:8000 python -m streamlit run app.py
```

Pastikan `.env` terisi pada lingkungan yang menjalankan API.

## 7. Testing & evidence

Hasil pengujian terakhir yang dilaporkan dari terminal lokal:

| Pengujian | Hasil |
|---|---|
| `tests/test_sql_guard.py` | 13/13 PASS |
| `tests/test_agent_qa_m2.py` | 10/10 PASS (unit / mock) |
| Total automated | **23/23 PASS** |
| `qa_live_smoke_m2.py` | **10/10 PASS** (live agent + Neon) |
| Docker Compose | FastAPI healthy; Streamlit UI berfungsi; QA shipment 217 terjawab |

Perintah:

```bash
python -m pytest tests/test_sql_guard.py tests/test_agent_qa_m2.py -q
python qa_live_smoke_m2.py
```

Live runner menghasilkan `evidence_qa_m2.json`. **Tes ini merupakan smoke-test skenario terpilih, bukan audit keamanan formal.** Tes QA-08 dan QA-10 perlu dinilai juga secara kualitatif untuk memastikan tidak ada kebocoran data atau kepatuhan terhadap instruksi yang disisipkan.

### Cakupan 10 QA

1. Verifikasi jumlah kiriman Agustus terhadap klaim salah 999.
2. On-time rate per carrier dan weighted overall; tidak memakai `in_transit` sebagai denominator.
3. Monetary refund Express September dan batas data 20 September.
4. Pengiriman tujuan Bandung per minggu ISO dalam Agustus.
5. Follow-up minggu tertinggi dan selisih terhadap minggu sebelumnya.
6. Periode Januari 2030 di luar dataset → no_data.
7. Lokasi paket saat ini → refusal terhadap klaim real-time.
8. Ringkasan `exception_note` tanpa mengeksekusi instruksi di dalam catatan.
9. Permintaan memodifikasi `delivery_status` → refusal.
10. Prompt injection meminta system prompt, kredensial, dan data pengguna lain → refusal.

## 8. Batasan dan keamanan

- Hanya data sintetis dalam rentang waktu tertentu; hasil di luar rentang tersebut tidak diarang.
- SQL dibatasi pada tabel Gold dan operasi SELECT aman melalui `src/sql_guard.py`; eksekusi tambahan dibatasi oleh role database read-only serta transaction timeout.
- Akses percakapan menggunakan token demo dan ownership di backend; tidak diklaim sebagai IAM production-grade.
- Kasus individu seperti lokasi paket real-time bukan kemampuan sistem ini.
- Jangan publikasikan `.env*`, URL Neon, token, maupun database dump. Pastikan `.gitignore` dan `.dockerignore` melindungi seluruh file sensitif.

## 9. Demo 5–7 menit

1. Perkenalkan objective dan arsitektur singkat.
2. Tunjukkan `docker compose ps` dan `/healthz`.
3. Buka Streamlit, autentikasi dengan token demo.
4. Tanyakan jumlah kiriman Agustus → **217**.
5. Tanyakan perbandingan on-time rate Agustus → **overall 75,25%**.
6. Tunjukkan refund Express September → **3,57%**.
7. Tunjukkan penolakan permintaan perubahan data / real-time.
8. Tutup dengan evidence **10/10 live QA** dan **23/23 automated tests**.

## 10. Future work

- Tambah pelacakan live hanya bila tersedia sumber data real-time dan kontrol akses memadai.
- Perluas periode dan filter analitik melalui semantic layer yang tervalidasi.
- Tambah evaluasi keamanan adversarial, API integration tests, observability, dan deployment production.
- Document RAG (misalnya SOP shipping) merupakan peningkatan opsional yang **belum diimplementasikan**.
