-- Dev seed — sample tags with active subscriptions valid for 30 days.

INSERT INTO tags (id, private_key, advertising_key, status)
VALUES
    (
        '00000000-0000-0000-0000-000000000001',
        decode('cbdfc678f5844ee5a253f648a47e9ed77fb47c27f65d5c2ab9d76e12', 'hex'),
        decode('27111704e5305b447c5bbbea26258cd69d17e9a63bf700d3a9062d1e', 'hex'),
        'assigned'
    ),
    (
        '00000000-0000-0000-0000-000000000002',
        decode('55c196d4133a55716e7f7a2c14d15898ee969ae457d6b9a6acbe4a39', 'hex'),
        decode('0265ae86e4c080269ccf5d867e7850346550aecf450940580fe37a24', 'hex'),
        'assigned'
    ),
    (
        '00000000-0000-0000-0000-000000000003',
        decode('df7a386d10db1dd63cc3f91dfa0e02365d97e57caf6e80278d03f1bf', 'hex'),
        decode('789b625d431df0bf8d88a710d274e2ae504a17edfa5eab01a5b6c2a0', 'hex'),
        'assigned'
    ),
    (
        '00000000-0000-0000-0000-000000000004',
        decode('46dafa8e4dd70f7686d6e8a8765f4b9acc00d1e30036ded2699a3f99', 'hex'),
        decode('9f82dfde7d3b0e18d7371653fee1b77a7a40f95415dd5ace1f099a0a', 'hex'),
        'assigned'
    ),
    (
        '00000000-0000-0000-0000-000000000005',
        decode('48e2aa498264c1ca99be610e2ecdb7872793c0fafda7322f72261540', 'hex'),
        decode('e8409eff260988457932f5ab0a6e246d435b0d941c7facce043a922a', 'hex'),
        'assigned'
    )
ON CONFLICT (id) DO UPDATE
    SET private_key     = EXCLUDED.private_key,
        advertising_key = EXCLUDED.advertising_key,
        status          = EXCLUDED.status;

INSERT INTO subscriptions (tag_id, active, expires_at)
VALUES
    ('00000000-0000-0000-0000-000000000001', true, NOW() + INTERVAL '30 days'),
    ('00000000-0000-0000-0000-000000000002', true, NOW() + INTERVAL '30 days'),
    ('00000000-0000-0000-0000-000000000003', true, NOW() + INTERVAL '30 days'),
    ('00000000-0000-0000-0000-000000000004', true, NOW() + INTERVAL '30 days'),
    ('00000000-0000-0000-0000-000000000005', true, NOW() + INTERVAL '30 days')
ON CONFLICT DO NOTHING;
