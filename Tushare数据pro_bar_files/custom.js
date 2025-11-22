var actionRun = function (routes) {
  var path = window.location.pathname;
  $.each(routes, function (i, route) {
    var type = route['type'];
    var pattern = route['pattern'];
    var action = route['action'];

    if (type == 'plain' && pattern == path) {
      return action()
    } else if (type == 'reg' && pattern.test(path)) {
      return action();
    }
  });
};

function getQuery(url, variable) {
  var query = url.split('?')[1];
  var vars = query.split('&');
  for (var i = 0; i < vars.length; i++) {
    var pair = vars[i].split('=');
    if (decodeURIComponent(pair[0]) == variable) {
      return decodeURIComponent(pair[1]);
    }
  }
  console.log('Query variable %s not found', variable);
}

function fallbackCopyTextToClipboard(text) {
  var textArea = document.createElement('textarea');
  textArea.value = text;

  document.body.prepend(textArea);
  textArea.focus();
  textArea.select();

  try {
    var successful = document.execCommand('copy');
  } catch (err) {
    successful = false;
  }

  document.body.removeChild(textArea);

  return successful;
}
// 复制的方法
function copyText(text, callback){ // text: 要复制的内容， callback: 回调
    var tag = document.createElement('input');
    tag.setAttribute('id', 'cp_hgz_input');
    tag.value = text;
    document.getElementsByTagName('body')[0].appendChild(tag);
    document.getElementById('cp_hgz_input').select();
    let result = document.execCommand('copy')
    document.getElementById('cp_hgz_input').remove();
    callback(result)
}

function initExtension() {

  if (!String.prototype.repeat) {
    String.prototype.repeat = function (count) {
      'use strict';
      if (this == null) {
        throw new TypeError('can\'t convert ' + this + ' to object');
      }
      var str = '' + this;
      count = +count;
      if (count != count) {
        count = 0;
      }
      if (count < 0) {
        throw new RangeError('repeat count must be non-negative');
      }
      if (count == Infinity) {
        throw new RangeError('repeat count must be less than infinity');
      }
      count = Math.floor(count);
      if (str.length == 0 || count == 0) {
        return '';
      }
      // Ensuring count is a 31-bit integer allows us to heavily optimize the
      // main part. But anyway, most current (August 2014) browsers can't handle
      // strings 1 << 28 chars or longer, so:
      if (str.length * count >= 1 << 28) {
        throw new RangeError('repeat count must not overflow maximum string size');
      }
      var rpt = '';
      for (var i = 0; i < count; i++) {
        rpt += str;
      }
      return rpt;
    }
  }
}

function getBrowserHeight() {
  return window.innerHeight || document.documentElement.clientHeight || document.body.clientHeight;
}

function getBrowerWidth() {
  return window.innerWidth || document.documentElement.clientWidth || document.body.clientWidth;
}

function initValidation() {

  if (typeof $.validator != 'function') {
    return
  }

  $.validator.addMethod("words", function (value, element) {
    var reg = /^[_0-9a-zA-Z]+$/;
    return this.optional(element) || reg.test(value);
  }, "please input letter, digit or underline");

  $.validator.addMethod("host", function (value, element) {
    var reg = /^[.\-_0-9a-zA-Z]+$/;
    return this.optional(element) || reg.test(value);
  }, "please input valid server host");

  $.validator.addMethod("en_and_cn", function (value, element) {
    var reg = /^[_0-9a-zA-Z\u4E00-\u9FA5]+$/;
    return this.optional(element) || reg.test(value);
  }, "please input chinese or english");

  $.validator.addMethod("password", function (value, element) {
    var reg = /^[=+_,@\-.!#$%^&*():;'"<>?\\|{}\[\]/0-9a-zA-Z]+$/;
    return this.optional(element) || reg.test(value);
  }, "password doesn't include space character");

  $.validator.addMethod("len", function (value, element, param) {
    return this.optional(element) || value.length == param;
  }, "password doesn't include space character");

  // 手机号码验证
  $.validator.addMethod("mobile", function (value, element) {
    var length = value.length;
    // var mobile = /^(13[0-9]{9})|(18[0-9]{9})|(14[0-9]{9})|(17[0-9]{9})|(15[0-9]{9})$/;
    var mobile = /^1[0-9]{10}$/;
    return this.optional(element) || (length == 11 && mobile.test(value));
  }, "mobile number must 11 bit digits");
}

/** 刷新验证码 */
function refreshCaptcha(img) {

  var action = img.attr('data-action');

  var url = '/captcha?action=' + action;
  $.get(url, function (data) {
    if (data.code == 0) {
      img.attr('src', data.data)
    } else {
      console.log(data.msg)
    }
  }, 'json');
}

function common() {

  $('#logout-btn').on('click', function () {
    $.get('/logout', function (data) {
      if (data.code == 0) {
        window.location.reload();
      }
    }, 'json');
    return false;
  });

}

function actionRegister() {

  $('#register-captcha-img').on('click', function () {
    refreshCaptcha($(this));
  });

  var sendRegCode = function () {

    var running = false;
    return function (that, account) {

      if (running == true) {
        return;
      }
      running = true;

      that.attr('disabled', 'disabled');

      var seconds = 60;
      $.get('/regcode?account=' + account, function (data) {
        var passSeconds = 0;
        if (data.code != 0) {
          alert(data.msg)
        } else {
          var timer = setInterval(function () {
            if (passSeconds == seconds) {
              clearTimeout(timer);
              that.html('发送验证码');
              that.removeAttr('disabled');
              running = false;
            } else if (passSeconds == 0) {
              that.html('已发送');
            } else {
              that.html((seconds - passSeconds) + '秒');
            }
            passSeconds++;
          }, 1000)
        }
      }, 'json')
    }
  }();

  var registerCaptcha = $('#register-captcha');
  registerCaptcha.on('blur', function () {
    var captcha = $(this).val();

    var msgPlace = $('#register-captcha-info');
    var label = msgPlace.find('label');
    if (captcha.length == 0) {
      msgPlace.attr('class', 'col-md-offset-2');
      label.html('图形验证码必须填写');
      return;
    }

    var src = $('#register-captcha-img').attr('src');
    var query = src.split('?')[1];

    var url = '/captcha/verify?';

    query += '&' + 'captcha=' + $(this).val();
    $.get(url, query, function (data) {
      if (data.code == 0) {
        msgPlace.attr('class', 'col-md-offset-2 hidden');
        label.html();
        $('#register-send_code').removeAttr('disabled');
      } else {
        msgPlace.attr('class', 'col-md-offset-2');
        label.html(data.msg);
        refreshCaptcha($('#register-captcha-img'));
      }
    }, 'json');
  });

  $('#register-send_code').on('click', function () {
    var account = $('#register-account').val();
    sendRegCode($(this), account);
  });

  function register(form) {
    var href = window.location.pathname + window.location.search
    $.post(href, $(form).serialize(), function (data) {
      var msgPlace = $('#register-common-info');
      var label = msgPlace.find('label');

      if (data.code == 0) {
        msgPlace.attr('class', 'col-md-offset-2');
        label.html(data.msg);
        label.attr('class', 'text-green');

        setTimeout(function () {
          window.location.href = '/login';
        }, 1000)
      } else {
        msgPlace.attr('class', 'col-md-offset-2');
        label.html(data.msg);
        label.attr('class', 'text-error')
      }
    }, 'json');
  }

  $('#register-form').validate({
    rules: {
      account: {
        required: true
      },
      password: {
        required: true,
        password: true,
        minlength: 6
      }
    },
    messages: {
      account: {
        required: '请填写邮箱或手机号码',
      },
      password: {
        required: '登录密码必须填写',
        password: '登录密码不可存在空字符',
        minlength: '登录密码不能少于6位'
      }
    },
    submitHandler: function (form) {
      register(form);
      return false;
    }
  });
}

function actionLogin() {

  $('#login-captcha-img, #resetpswd-captcha-img').on('click', function () {
    refreshCaptcha($(this));
  });

  var loginCaptcha = $('#login-captcha');
  var checkLoginCaptcha = function (callback, form) {

    var msgPlace = $('#login-common-info');
    var label = msgPlace.find('label');
    var captcha = $('#login-captcha').val();

    if (captcha.length == 0) {
      msgPlace.attr('class', 'col-md-offset-2');
      label.attr('class', 'text-error');
      label.html('图形验证码必须填写');
      return;
    } else {
      msgPlace.attr('class', 'col-md-offset-2 hidden');
      label.attr('class', '');
      label.html();
    }

    var src = $('#login-captcha-img').attr('src');
    var query = src.split('?')[1];

    var url = '/captcha/verify?';

    query += '&' + 'captcha=' + captcha;
    $.get(url, query, function (data) {
      if (data.code == 0) {
        if (typeof callback == 'function') {
          callback(form);
        } else {
          msgPlace.attr('class', 'col-md-offset-2 hidden');
          label.attr('class', '');
          label.html();
        }
      } else {
        msgPlace.attr('class', 'col-md-offset-2');
        label.attr('class', 'text-error');
        label.html('图形验证码输入错误');
        refreshCaptcha($('#login-captcha-img'));
      }
    }, 'json');
  };

  loginCaptcha.on('blur', function () {
    checkLoginCaptcha();
  });

  function login(form) {
    var msgPlace = $('#login-common-info');
    var label = msgPlace.find('label');

    $.post('/login', $(form).serialize(), function (data) {
      if (data.code == 0) {
        msgPlace.attr('class', 'col-md-offset-2');
        label.attr('class', 'text-green');
        label.html(data.msg);
        setTimeout(function () {
          window.location.reload();
        }, 1000);
      } else {
        msgPlace.attr('class', 'col-md-offset-2');
        label.attr('class', 'text-error');
        label.html(data.msg);
        refreshCaptcha($('#login-captcha-img'));
      }
    }, 'json');
  }

  var validate = {
    rules: {
      account: {
        required: true
      },
      password: {
        required: true,
        password: true,
        minlength: 6
      }
    },
    messages: {
      account: {
        required: '登录账号必须填写'
      },
      password: {
        required: '密码必须填写',
        password: '密码不能包含空字符',
        minlength: '密码不能少于6位'
      }
    },
    submitHandler: function (form) {
      checkLoginCaptcha(login, form);
      return false;
    }
  };

  $('#login-form').validate(validate);
}

function actionResetPswd() {

  $('#resetpswd-captcha-img').on('click', function () {
    refreshCaptcha($(this));
  });

  var sendResetCode = function () {

    var running = false;
    return function (that, account) {

      if (running == true) {
        return;
      }
      running = true;

      that.attr('disabled', 'disabled');

      var seconds = 60;
      $.get('/resetcode?account=' + account, function (data) {
        var passSeconds = 0;
        if (data.code != 0) {
          alert(data.msg)
        } else {
          var timer = setInterval(function () {
            if (passSeconds == seconds) {
              clearTimeout(timer);
              that.html('发送验证码');
              that.removeAttr('disabled');
              running = false;
            } else if (passSeconds == 0) {
              that.html('已发送');
            } else {
              that.html((seconds - passSeconds) + '秒');
            }
            passSeconds++;
          }, 1000)
        }
      }, 'json')
    }
  }();

  var resetpswdCaptcha = $('#resetpswd-captcha');
  resetpswdCaptcha.on('blur', function () {
    var captcha = $(this).val();

    var msgPlace = $('#resetpswd-captcha-info');
    var label = msgPlace.find('label');
    if (captcha.length == 0) {
      msgPlace.attr('class', 'col-md-offset-2');
      label.html('图形验证码必须填写');
      return;
    }

    var src = $('#resetpswd-captcha-img').attr('src');
    var query = src.split('?')[1];

    var url = '/captcha/verify?';

    query += '&' + 'captcha=' + $(this).val();
    $.get(url, query, function (data) {
      if (data.code == 0) {
        msgPlace.attr('class', 'col-md-offset-2 hidden');
        label.html();
        $('#resetpswd-send_code').removeAttr('disabled');
      } else {
        msgPlace.attr('class', 'col-md-offset-2');
        label.html(data.msg);
      }
    }, 'json');
  });

  $('#resetpswd-send_code').on('click', function () {
    var account = $('#resetpswd-account').val();
    sendResetCode($(this), account);
  });

  function resetpswd(form) {

    $.post('/resetpswd', $(form).serialize(), function (data) {
      var msgPlace = $('#resetpswd-common-info');
      var label = msgPlace.find('label');

      if (data.code == 0) {
        msgPlace.attr('class', 'col-md-offset-2');
        label.html(data.msg);
        label.attr('class', 'text-green');

        setTimeout(function () {
          window.location.href = '/login';
        }, 1000)
      } else {
        msgPlace.attr('class', 'col-md-offset-2');
        label.html(data.msg);
        label.attr('class', 'text-error')
      }
    }, 'json');
  }

  $('#resetpswd-form').validate({
    rules: {
      account: {
        required: true
      },
      password: {
        required: true,
        password: true,
        minlength: 6
      }
    },
    messages: {
      account: {
        required: '请输入账号，邮箱或手机号码'
      },
      password: {
        required: '新的密码必须填写',
        password: '新的密码不可存在空字符',
        minlength: '新的密码不能少于6位'
      }
    },
    submitHandler: function (form) {
      resetpswd(form);
      return false;
    }
  });
}

function actionUserInfo() {

  function modifyUser(form) {
    var msgPlace = $('#message');
    var label = msgPlace.find('span');
    $.post('/user/info', $(form).serialize(), function (data) {
      label.html(data.msg);
      if (data.code == 0) {
        msgPlace.attr('class', 'col-md-offset-1');
        label.attr('class', 'text-green');
//        label.html(data.msg);

        setTimeout(function () {
          window.location.reload();
        }, 1000)
      } else {
        msgPlace.attr('class', 'col-md-offset-1');
        label.attr('class', 'error');
      }
    }, 'json');
  }

  $('#user-form').validate({
    rules: {
      username: {
        en_and_cn: true
      },
    },
    messages: {
      username: {
        en_and_cn: '昵称由英文和下划线'
      },
    },
    submitHandler: function (form) {
      modifyUser(form);
      return false;
    }
  })
}

function actionUserToken() {

  var starToken = '********'.repeat(7);
  var tokenEle = $('#token');
  var tokenValEle = $('#token-value');
  var tokenValue = tokenValEle.val();
  var tokenBtn = $('#visible-token');
  var messageEle = $('#message');

  function hideToken() {
    tokenEle.val(starToken);
    tokenEle.attr('style', 'font-size: 21px;padding-top:10px');
    tokenBtn.html('<i class="fa fa-eye-slash">')
  }

  function showToken() {
    tokenEle.val(tokenValue);
    tokenEle.attr('style', 'font-size: 14px;');
    tokenBtn.html('<i class="fa fa-eye">')
  }

  hideToken();
  tokenBtn.on('click', function () {
    var value = tokenEle.val();
    if (value == starToken) {
      showToken();
    } else {
      hideToken();
    }
  });

  $('#copy-token').on('click', function () {
    copyText(tokenValue, function (success) {
      if (success) {
        messageEle.attr('class', 'text-green');
        messageEle.html('接口TOKEN成功复制到剪贴板！');
      } else {
        messageEle.attr('class', 'text-red');
        messageEle.html('抱歉，复制操作失败！')
      }

      /** 清除消息 */
      setTimeout(function () {
        messageEle.html('');
      }, 2000);
    });

    return false;
  });

  $('#refresh-token').on('click', function () {

    messageEle.attr('class', 'text-gray');
    messageEle.html('刷新中...');

    $.post('/user/token', function (data) {
      if (data.code == 0) {
        messageEle.attr('class', 'text-green');

        /** update token */
        tokenValue = data.data;
        tokenValEle.val(tokenValue);
        if (tokenEle.val() != starToken) {
          tokenEle.val(data.data);
        }
      } else {
        messageEle.attr('class', 'text-red');
      }
      messageEle.html(data.msg);

      /** 清除消息 */
      setTimeout(function () {
        messageEle.html('');
      }, 2000);
    }, 'json')
  })
}

function actionUserSecure() {

  var passwordModal = $('#password-modal');
  $('#modify-password').on('click', function () {
    passwordModal.modal('show');
  });

  function modifyPassword(form) {
    var msgPlace = $('#pwd-message');
    var label = msgPlace.find('label');

    $.post('/modifypswd', $(form).serialize(), function (data) {
      if (data.code == 0) {
        msgPlace.attr('class', 'col-md-offset-2');
        label.attr('class', 'text-green');
        setTimeout(function () {
          passwordModal.modal('hide');
        }, 1000);
      } else {
        msgPlace.attr('class', 'col-md-offset-2');
        label.attr('class', 'text-red');
      }
      label.html(data.msg);
    }, 'json')
  }

  $('#password-form').validate({
    rules: {
      src_password: {
        required: true,
        password: true
      },
      password: {
        required: true,
        password: true,
        minlength: 6
      },
      confirm_password: {
        required: true,
        equalTo: '#user-password'
      }
    },
    messages: {
      src_password: {
        required: '原始密码必须填写',
        password: '不能包含空白字符'
      },
      password: {
        required: '新的密码必须填写',
        minlength: '新的密码不能少于6位',
        password: '不嫩包含空白字符'
      },
      confirm_password: {
        required: '确认密码必须填写',
        equalTo: '两次密码输入不一致'
      }
    },
    submitHandler: function (form) {
      modifyPassword(form);
      return false;
    }
  });

  var phoneModal = $('#phone-modal');
  $('#modify-phone').on('click', function () {
    phoneModal.modal('show');
  });

  function bindPhone(form) {
    var msgPlace = $('#phone-message');
    var label = msgPlace.find('label');

    $.post('/bindphone', $(form).serialize(), function (data) {
      if (data.code == 0) {
        msgPlace.attr('class', 'col-md-offset-2');
        label.attr('class', 'text-green');
        setTimeout(function () {
          window.location.reload()
        }, 1000);
      } else {
        msgPlace.attr('class', 'col-md-offset-2');
        label.attr('class', 'text-red');
      }
      label.html(data.msg);
    }, 'json')
  }

  $('#phone-form').validate({
    rules: {
      phone: {
        required: true,
        mobile: true
      }
    },
    messages: {
      phone: {
        required: '请输入手机号码',
        mobile: '请输入正确的手机号码'
      }
    },
    submitHandler: function (form) {
      bindPhone(form);
      return false;
    }
  });

  var sendBindPhoneCode = function () {

    var running = false;
    return function (that, email) {

      if (running == true) {
        return;
      }
      running = true;

      that.attr('disabled', 'disabled');

      var seconds = 60;
      $.get('/bindphone?phone=' + email, function (data) {
        var passSeconds = 0;
        if (data.code != 0) {
          alert(data.msg)
        } else {
          var timer = setInterval(function () {
            if (passSeconds == seconds) {
              clearTimeout(timer);
              that.html('发送验证码');
              that.removeAttr('disabled');
              running = false;
            } else if (passSeconds == 0) {
              that.html('已发送');
            } else {
              that.html((seconds - passSeconds) + '秒');
            }
            passSeconds++;
          }, 1000)
        }
      }, 'json')
    }
  }();

  $('#phone-send_code').on('click', function () {
    var phone = $('#phone').val();
    sendBindPhoneCode($(this), phone);
  });

  var emailModal = $('#email-modal');
  $('#modify-email').on('click', function () {
    emailModal.modal('show');
  });

  var sendBindEmailCode = function () {

    var running = false;
    return function (that, email) {

      if (running == true) {
        return;
      }
      running = true;

      that.attr('disabled', 'disabled');

      var seconds = 60;
      $.get('/bindemail?email=' + email, function (data) {
        var passSeconds = 0;
        if (data.code != 0) {
          alert(data.msg)
        } else {
          var timer = setInterval(function () {
            if (passSeconds == seconds) {
              clearTimeout(timer);
              that.html('发送验证码');
              that.removeAttr('disabled');
              running = false;
            } else if (passSeconds == 0) {
              that.html('已发送');
            } else {
              that.html((seconds - passSeconds) + '秒');
            }
            passSeconds++;
          }, 1000)
        }
      }, 'json')
    }
  }();

  function bindEmail(form) {
    var msgPlace = $('#email-message');
    var label = msgPlace.find('label');

    $.post('/bindemail', $(form).serialize(), function (data) {
      if (data.code == 0) {
        msgPlace.attr('class', 'col-md-offset-2');
        label.attr('class', 'text-green');
        setTimeout(function () {
          window.location.reload()
        }, 1000);
      } else {
        msgPlace.attr('class', 'col-md-offset-2');
        label.attr('class', 'text-red');
      }
      label.html(data.msg);
    }, 'json')
  }

  $('#email-send_code').on('click', function () {
    var email = $('#email').val();
    sendBindEmailCode($(this), email);
  });

  $('#email-form').validate({
    rules: {
      email: {
        required: true,
        email: true
      }
    },
    messages: {
      phone: {
        required: '请输入邮箱',
        mobile: '请输入正确的邮箱格式'
      }
    },
    submitHandler: function (form) {
      bindEmail(form);
      return false;
    }
  });
}

function actionDocument() {
}

common();
initExtension();
initValidation();

var routes = [
  {type: 'plain', pattern: "/login", action: actionLogin},
  {type: 'plain', pattern: '/register', action: actionRegister},
  {type: 'plain', pattern: '/resetpswd', action: actionResetPswd},
  {type: 'plain', pattern: '/user/info', action: actionUserInfo},
  {type: 'plain', pattern: '/user/token', action: actionUserToken},
  {type: 'plain', pattern: '/user/secure', action: actionUserSecure},
  {type: 'reg', pattern: /\/document\/([0-9]+)/, action: actionDocument}
];

actionRun(routes);
