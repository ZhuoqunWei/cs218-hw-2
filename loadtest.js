import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 20,
  duration: "60s",
  thresholds: {
    http_req_failed: ["rate<0.01"],   // < 1% errors
    http_req_duration: ["p(95)<500"], // p95 < 500ms
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";

export default function () {
  // POST /items
  const payload = JSON.stringify({ name: `item-${__VU}-${__ITER}`, value: __ITER });
  const postRes = http.post(`${BASE_URL}/items`, payload, {
    headers: { "Content-Type": "application/json" },
  });
  check(postRes, { "POST /items 201": (r) => r.status === 201 });

  const id = postRes.json("id");
  if (!id) return;

  // GET /items/<id>
  const getRes = http.get(`${BASE_URL}/items/${id}`);
  check(getRes, {
    "GET /items/<id> 200": (r) => r.status === 200,
    "item name matches": (r) => r.json("name") === `item-${__VU}-${__ITER}`,
  });

  sleep(0.1);
}
