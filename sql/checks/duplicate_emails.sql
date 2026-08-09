SELECT LOWER(email) AS email_normalized, COUNT(*) AS total
FROM mdl_user
WHERE deleted = 0
  AND email IS NOT NULL
  AND email <> ''
GROUP BY LOWER(email)
HAVING COUNT(*) > 1
ORDER BY total DESC, email_normalized;
