

def test_landing(client):
    '''Make sure we get the landing page from a basic root path request.'''
    response = client.get('/')
    assert b"CodeHelp is a coding and CS assistant." in response.data
