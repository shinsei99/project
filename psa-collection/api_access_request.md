# PSA Public API 利用承認の依頼メール（下書き）

`GetImagesByCertNumber` / `GetByCertNumber` が 403 `Access to this API is limited to approved customers`
を返すため、PSAに利用承認を依頼する。

- **宛先**: collectors-apis@collectors.com
- **件名**: Request for Public API access approval — personal collection management

---

Hello,

I have a PSA account and generated an access token from
https://www.psacard.com/publicapi, but every request returns HTTP 403 with
`{"Message":"Access to this API is limited to approved customers."}`.

Requests without a valid token return 429 instead, so the token is clearly being
recognized — it appears my account simply has not been approved for API access.

Could you please approve my account, or let me know what the approval process is?

**Details**

- PSA account email: （PSAアカウントのメールアドレス）
- Endpoints attempted:
  - `GET /publicapi/cert/GetByCertNumber/98769002`
  - `GET /publicapi/cert/GetImagesByCertNumber/98769002`
- Header sent: `Authorization: bearer <token generated on the publicapi page>`
- Response: `403 {"Message":"Access to this API is limited to approved customers."}`

**Intended use**

Personal, non-commercial. I own roughly 870 PSA-graded cards and am building a
small private tool for myself to keep track of which cards I hold and where they
are physically stored. I would like to display the PSA card images alongside my
own inventory records so I can identify each card visually. The data stays on my
own machine and is not redistributed or published.

The free tier of 100 requests per day is sufficient for my needs.

Thank you for your help.

Best regards,
（お名前）

---

## 承認後にやること

```bash
cd ~/psa-collection
python3 fetch_images.py --status   # 状況確認
python3 fetch_images.py            # 100件取得（毎日実行すれば4日で完了）
```

トークンは `data/psa_api.json` に保存済み。承認が下りればコード変更なしでそのまま動く。
