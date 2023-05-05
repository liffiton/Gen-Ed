

def test_landing(client):
    '''Make sure we get the landing page from a basic root path request.'''
    response = client.get('/')
    assert b"CodeHelp is a tool that can help you while you code." in response.data
