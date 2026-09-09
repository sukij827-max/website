# Email Marketplace

Website marketplace untuk pengajuan alamat email dengan review manual admin.

## Fitur
- Register / login / logout
- Dashboard saldo dan riwayat
- Pengajuan banyak email dalam satu batch
- Review email satu per satu: pending / accepted / rejected
- Payout otomatis berdasarkan harga saat batch dibuat
- Admin: user management dan penyesuaian saldo manual
- Admin: pengaturan harga per email dan aturan tanpa deploy ulang
- Audit log
- PostgreSQL via `DATABASE_URL`

## Environment variables
- `DATABASE_URL` — PostgreSQL connection string
- `SECRET_KEY` — random secret untuk session
- `ADMIN_USERNAME` — username admin (default: `admin`)
- `ADMIN_PASSWORD` — password admin (default: `change-me-now`, wajib diganti)
- `DEFAULT_EMAIL_PRICE` — harga awal per email, default `500`

Jangan pernah memasukkan password, OTP, recovery code, atau kredensial akun pada form pengajuan.
