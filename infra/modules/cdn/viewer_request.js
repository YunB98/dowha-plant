// CloudFront Function (viewer-request), 기본 경로(정적 사이트)에만 연결한다.
// 1. www.<도메인> → <도메인> 영구 이동
// 2. Next.js 정적 빌드(trailingSlash: true)의 폴더형 주소를 index.html로 바꾼다
//    /guides/monstera  → /guides/monstera/index.html
//    /guides/          → /guides/index.html
function handler(event) {
  var request = event.request;
  var host = request.headers.host ? request.headers.host.value : '';

  if (host.indexOf('www.') === 0) {
    var query = Object.keys(request.querystring)
      .map(function (k) {
        var v = request.querystring[k];
        return v.value ? k + '=' + v.value : k;
      })
      .join('&');
    return {
      statusCode: 301,
      statusDescription: 'Moved Permanently',
      headers: {
        location: { value: 'https://' + host.substring(4) + request.uri + (query ? '?' + query : '') }
      }
    };
  }

  var uri = request.uri;
  if (uri.endsWith('/')) {
    request.uri = uri + 'index.html';
  } else if (uri.split('/').pop().indexOf('.') === -1) {
    request.uri = uri + '/index.html';
  }
  return request;
}
