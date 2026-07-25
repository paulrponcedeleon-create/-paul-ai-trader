def test_mobile_lite_requires_auth(client):
    response = client.get('/api/mobile', follow_redirects=False)
    assert response.status_code in {401, 403}


def test_mobile_lite_uses_real_links_and_no_background_intervals(client):
    client.post('/api/login', json={'password': 'test-password'})
    response = client.get('/api/mobile?tab=overview')
    assert response.status_code == 200
    html = response.text
    assert 'Modo ligero' in html
    assert 'href="/api/mobile?tab=markets"' in html
    assert 'href="/api/mobile?tab=paper"' in html
    assert 'setInterval' not in html
    assert 'setTimeout(()=>c.abort(),6000)' in html


def test_mobile_lite_renders_requested_tab(client):
    client.post('/api/login', json={'password': 'test-password'})
    response = client.get('/api/mobile?tab=markets')
    assert response.status_code == 200
    assert 'Compra simulada manual' in response.text
    assert 'class="active">Mercados</a>' in response.text
